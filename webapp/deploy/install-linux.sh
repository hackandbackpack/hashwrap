#!/bin/bash
# HashWrap Linux Production Deployment Script
# Automated installation for Apache + mod_wsgi deployment

set -e  # Exit on any error

INSTALL_DIR="/opt/hashwrap"
SERVICE_USER="hashwrap"
DOMAIN="hashwrap.local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/debian_version ]]; then
        OS="debian"
        APACHE_SERVICE="apache2"
        APACHE_CONFIG_DIR="/etc/apache2/sites-available"
    elif [[ -f /etc/redhat-release ]]; then
        OS="redhat"
        APACHE_SERVICE="httpd"
        APACHE_CONFIG_DIR="/etc/httpd/conf.d"
    else
        log_error "Unsupported operating system"
        exit 1
    fi
    
    log_info "Detected OS: $OS"
}

install_dependencies() {
    log_info "Installing system dependencies..."
    
    if [[ $OS == "debian" ]]; then
        apt-get update
        apt-get install -y \
            apache2 \
            libapache2-mod-wsgi-py3 \
            python3 \
            python3-venv \
            python3-pip \
            sqlite3 \
            hashcat \
            nvidia-smi \
            curl \
            openssl \
            git
    elif [[ $OS == "redhat" ]]; then
        yum update -y
        yum install -y \
            httpd \
            python3-mod_wsgi \
            python3 \
            python3-pip \
            sqlite \
            hashcat \
            curl \
            openssl \
            git
    fi
    
    log_success "Dependencies installed"
}

create_user() {
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_info "Creating service user: $SERVICE_USER"
        useradd --system --shell /bin/false --home-dir $INSTALL_DIR --create-home $SERVICE_USER
        log_success "Service user created"
    else
        log_info "Service user already exists"
    fi
}

setup_directories() {
    log_info "Setting up application directories..."
    
    # Create main directories
    mkdir -p $INSTALL_DIR/webapp
    mkdir -p $INSTALL_DIR/venv
    mkdir -p /var/log/hashwrap
    
    # Create data directories
    mkdir -p $INSTALL_DIR/webapp/data/{uploads,results}
    mkdir -p $INSTALL_DIR/webapp/logs
    mkdir -p $INSTALL_DIR/webapp/wordlists
    
    # Set permissions
    chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    chown -R $SERVICE_USER:$SERVICE_USER /var/log/hashwrap
    chmod 755 $INSTALL_DIR
    chmod 750 $INSTALL_DIR/webapp/data
    
    log_success "Directories created"
}

install_application() {
    log_info "Installing HashWrap application..."
    
    # Copy application files
    cp -r ../webapp/* $INSTALL_DIR/webapp/
    
    # Create Python virtual environment
    python3 -m venv $INSTALL_DIR/venv
    source $INSTALL_DIR/venv/bin/activate
    
    # Install Python dependencies
    pip install --upgrade pip
    pip install flask werkzeug psutil requests
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    
    # Make scripts executable
    chmod +x $INSTALL_DIR/webapp/test_system.py
    chmod +x $INSTALL_DIR/webapp/validate_deployment.py
    chmod +x $INSTALL_DIR/webapp/hashcat_worker.py
    
    log_success "Application installed"
}

configure_apache() {
    log_info "Configuring Apache web server..."
    
    # Enable required modules
    if [[ $OS == "debian" ]]; then
        a2enmod ssl
        a2enmod rewrite
        a2enmod headers
        a2enmod deflate
        a2enmod wsgi
    fi
    
    # Copy virtual host configuration
    cp apache-hashwrap.conf $APACHE_CONFIG_DIR/
    
    # Enable the site
    if [[ $OS == "debian" ]]; then
        a2ensite apache-hashwrap.conf
        a2dissite 000-default.conf
    fi
    
    log_success "Apache configured"
}

generate_ssl_certificate() {
    log_info "Generating self-signed SSL certificate..."
    
    mkdir -p /etc/ssl/private
    
    # Generate private key and certificate
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/hashwrap.key \
        -out /etc/ssl/certs/hashwrap.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
    
    # Set secure permissions
    chmod 600 /etc/ssl/private/hashwrap.key
    chmod 644 /etc/ssl/certs/hashwrap.crt
    
    log_success "SSL certificate generated"
}

install_systemd_service() {
    log_info "Installing systemd service..."
    
    # Copy service file
    cp hashwrap-worker.service /etc/systemd/system/
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable hashwrap-worker
    
    log_success "Systemd service installed"
}

initialize_database() {
    log_info "Initializing database..."
    
    # Run as service user
    sudo -u $SERVICE_USER bash << EOF
cd $INSTALL_DIR/webapp
source $INSTALL_DIR/venv/bin/activate
python3 -c "
from app_fixed import init_db
init_db()
print('Database initialized')
"
EOF
    
    log_success "Database initialized"
}

setup_basic_wordlist() {
    log_info "Setting up basic wordlists..."
    
    # Create basic wordlist if rockyou.txt not available
    if [[ ! -f $INSTALL_DIR/webapp/wordlists/rockyou.txt ]]; then
        cat > $INSTALL_DIR/webapp/wordlists/common-passwords.txt << 'EOF'
password
123456
password123
admin
letmein
welcome
monkey
1234567890
qwerty
abc123
Password1
admin123
root
toor
pass
test
user
guest
login
changeme
EOF
        
        log_warning "rockyou.txt not found, created basic wordlist"
        log_info "Download rockyou.txt to $INSTALL_DIR/webapp/wordlists/ for better results"
    fi
    
    chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR/webapp/wordlists
}

start_services() {
    log_info "Starting services..."
    
    # Start and enable Apache
    systemctl enable $APACHE_SERVICE
    systemctl restart $APACHE_SERVICE
    
    # Start worker service
    systemctl start hashwrap-worker
    
    log_success "Services started"
}

run_validation() {
    log_info "Running deployment validation..."
    
    # Wait a moment for services to start
    sleep 5
    
    # Run validation as service user
    sudo -u $SERVICE_USER bash << EOF
cd $INSTALL_DIR/webapp
source $INSTALL_DIR/venv/bin/activate
python3 validate_deployment.py
EOF
    
    if [[ $? -eq 0 ]]; then
        log_success "Validation passed"
    else
        log_warning "Some validation checks failed - review above output"
    fi
}

print_completion_info() {
    echo
    echo "=========================================="
    echo "  HashWrap Installation Complete!"
    echo "=========================================="
    echo
    echo "🌐 Web Interface:"
    echo "   https://$DOMAIN/"
    echo "   http://$DOMAIN:8080/ (development)"
    echo
    echo "🔐 Default Login:"
    echo "   Username: admin"
    echo "   Password: admin"
    echo "   (Change this immediately!)"
    echo
    echo "📁 Installation Directory:"
    echo "   $INSTALL_DIR/webapp"
    echo
    echo "📋 Service Management:"
    echo "   systemctl status hashwrap-worker"
    echo "   systemctl restart hashwrap-worker"
    echo "   systemctl status $APACHE_SERVICE"
    echo
    echo "📊 Logs:"
    echo "   /var/log/hashwrap/hashwrap.log"
    echo "   /var/log/apache2/hashwrap_error.log"
    echo "   journalctl -u hashwrap-worker"
    echo
    echo "🧪 Testing:"
    echo "   cd $INSTALL_DIR/webapp"
    echo "   sudo -u $SERVICE_USER python3 test_system.py"
    echo
    echo "⚠️  Security Reminders:"
    echo "   - Change default admin password"
    echo "   - Review firewall settings"
    echo "   - Update SSL certificate for production"
    echo "   - Regular security updates"
    echo
}

main() {
    echo "🚀 HashWrap Linux Deployment Installer"
    echo "======================================"
    
    check_root
    detect_os
    install_dependencies
    create_user
    setup_directories
    install_application
    configure_apache
    generate_ssl_certificate
    install_systemd_service
    initialize_database
    setup_basic_wordlist
    start_services
    run_validation
    
    print_completion_info
    
    log_success "HashWrap deployment completed successfully!"
}

# Handle interrupts gracefully
trap 'log_error "Installation interrupted"; exit 1' INT TERM

# Run main installation
main "$@"