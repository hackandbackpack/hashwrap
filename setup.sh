#!/bin/bash
# HashWrap Setup Script
# Automated installation with Docker auto-install for penetration testers

set -euo pipefail

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/setup.log"
DOCKER_COMPOSE_VERSION="2.24.5"

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

print_header() {
    clear
    echo -e "${BLUE}${BOLD}"
    echo "=================================================="
    echo "           HashWrap Setup Script"
    echo "    Automated Pentest Hash Cracking Setup"
    echo "=================================================="
    echo -e "${NC}"
    log "HashWrap setup started"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    log "INFO: $1"
}

print_step() {
    echo -e "${BOLD}${BLUE}🔄 $1${NC}"
    log "STEP: $1"
}

# System detection
detect_os() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
        OS_CODENAME=${VERSION_CODENAME:-""}
    elif [[ -f /etc/redhat-release ]]; then
        OS="rhel"
        OS_VERSION=$(grep -oE '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
    else
        print_error "Cannot detect operating system"
        exit 1
    fi
    
    print_info "Detected OS: $OS $OS_VERSION"
    log "OS Detection: $OS $OS_VERSION $OS_CODENAME"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is not recommended for Docker operations."
        if [[ -z "${SUDO_USER:-}" ]]; then
            print_error "Please run this script with 'sudo' or as a regular user with sudo privileges"
            exit 1
        fi
        REAL_USER="$SUDO_USER"
        REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
    else
        REAL_USER="$USER"
        REAL_HOME="$HOME"
    fi
    
    print_info "Setup user: $REAL_USER"
}

# Check system requirements
check_system_requirements() {
    print_step "Checking system requirements"
    
    # Check available disk space (need at least 5GB)
    available_space=$(df "$SCRIPT_DIR" | tail -1 | awk '{print $4}')
    available_gb=$((available_space / 1024 / 1024))
    
    if [[ $available_gb -lt 5 ]]; then
        print_error "Insufficient disk space. Need at least 5GB, have ${available_gb}GB"
        exit 1
    fi
    
    print_success "Disk space: ${available_gb}GB available"
    
    # Check memory (recommend at least 2GB)
    total_mem=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    total_gb=$((total_mem / 1024 / 1024))
    
    if [[ $total_gb -lt 2 ]]; then
        print_warning "Low memory: ${total_gb}GB (recommended: 2GB+)"
    else
        print_success "Memory: ${total_gb}GB available"
    fi
    
    # Check for required tools
    for tool in curl wget sudo; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            print_error "Required tool '$tool' not found"
            exit 1
        fi
    done
    
    print_success "System requirements check completed"
}

# Install Docker based on OS
install_docker() {
    if command -v docker >/dev/null 2>&1; then
        print_info "Docker is already installed"
        docker --version
        return 0
    fi
    
    print_step "Installing Docker"
    
    case "$OS" in
        ubuntu|debian)
            install_docker_debian
            ;;
        rhel|centos|rocky|almalinux)
            install_docker_rhel
            ;;
        fedora)
            install_docker_fedora
            ;;
        arch|manjaro)
            install_docker_arch
            ;;
        *)
            print_error "Unsupported OS: $OS"
            print_info "Please install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac
    
    # Configure Docker service
    systemctl enable docker
    systemctl start docker
    
    # Add user to docker group
    if ! groups "$REAL_USER" | grep -q docker; then
        usermod -aG docker "$REAL_USER"
        print_warning "Added $REAL_USER to docker group. You may need to log out and back in."
    fi
    
    print_success "Docker installation completed"
}

install_docker_debian() {
    print_info "Installing Docker on Debian/Ubuntu"
    
    # Update package index
    apt-get update
    
    # Install prerequisites
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/${OS}/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${OS} \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
}

install_docker_rhel() {
    print_info "Installing Docker on RHEL/CentOS"
    
    # Install required packages
    yum install -y yum-utils
    
    # Add Docker repository
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    
    # Install Docker Engine
    yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
}

install_docker_fedora() {
    print_info "Installing Docker on Fedora"
    
    # Install required packages
    dnf -y install dnf-plugins-core
    
    # Add Docker repository
    dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
    
    # Install Docker Engine
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
}

install_docker_arch() {
    print_info "Installing Docker on Arch Linux"
    
    # Update package database
    pacman -Sy
    
    # Install Docker
    pacman -S --noconfirm docker docker-compose
}

# Install Docker Compose if not available
install_docker_compose() {
    # Check if Docker Compose plugin is available
    if docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose plugin is available"
        return 0
    fi
    
    # Check if standalone docker-compose is available
    if command -v docker-compose >/dev/null 2>&1; then
        print_success "Docker Compose standalone is available"
        return 0
    fi
    
    print_step "Installing Docker Compose"
    
    # Install Docker Compose plugin (modern approach)
    case "$OS" in
        ubuntu|debian)
            apt-get install -y docker-compose-plugin
            ;;
        rhel|centos|rocky|almalinux)
            yum install -y docker-compose-plugin
            ;;
        fedora)
            dnf install -y docker-compose-plugin
            ;;
        arch|manjaro)
            # Already installed with docker package
            print_info "Docker Compose included with Arch Docker package"
            ;;
        *)
            # Fallback to standalone installation
            install_docker_compose_standalone
            ;;
    esac
    
    print_success "Docker Compose installation completed"
}

install_docker_compose_standalone() {
    print_info "Installing standalone Docker Compose"
    
    # Determine architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) COMPOSE_ARCH="x86_64" ;;
        aarch64) COMPOSE_ARCH="aarch64" ;;
        *) print_error "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    
    # Download and install
    curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${COMPOSE_ARCH}" \
        -o /usr/local/bin/docker-compose
    
    chmod +x /usr/local/bin/docker-compose
    
    # Verify installation
    docker-compose --version
}

# Install NVIDIA Container Toolkit for GPU support
install_nvidia_support() {
    print_step "Checking for NVIDIA GPU support"
    
    # Check if NVIDIA driver is installed
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        print_info "No NVIDIA drivers detected. Skipping GPU support."
        return 0
    fi
    
    # Check if Container Toolkit is already installed
    if docker info 2>/dev/null | grep -q nvidia; then
        print_success "NVIDIA Container Toolkit already configured"
        return 0
    fi
    
    print_info "Installing NVIDIA Container Toolkit"
    
    case "$OS" in
        ubuntu|debian)
            # Add NVIDIA repository
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
            curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
            curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
                tee /etc/apt/sources.list.d/nvidia-docker.list
            
            apt-get update
            apt-get install -y nvidia-docker2
            ;;
        rhel|centos|rocky|almalinux)
            # Add NVIDIA repository
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
            curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | \
                tee /etc/yum.repos.d/nvidia-docker.repo
            
            yum install -y nvidia-docker2
            ;;
        *)
            print_warning "NVIDIA Container Toolkit auto-install not supported for $OS"
            print_info "Install manually: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/"
            return 0
            ;;
    esac
    
    # Restart Docker to load the new runtime
    systemctl restart docker
    
    print_success "NVIDIA Container Toolkit installation completed"
    
    # Test GPU access
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi >/dev/null 2>&1; then
        print_success "GPU access verified"
    else
        print_warning "GPU access test failed. Check NVIDIA Container Toolkit configuration."
    fi
}

# Setup application directories and files
setup_application() {
    print_step "Setting up HashWrap application"
    
    # Create data directories
    mkdir -p data/uploads data/results webapp/logs wordlists
    
    # Set proper ownership
    chown -R "$REAL_USER:$REAL_USER" data wordlists webapp/logs
    chmod 755 data/uploads data/results
    
    print_success "Application directories created"
    
    # Create basic wordlist if none exists
    if [[ ! -f "wordlists/common-passwords.txt" ]]; then
        print_info "Creating basic wordlist"
        cat > wordlists/common-passwords.txt << 'EOF'
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
administrator
guest
user
test
demo
login
changeme
password1
123123
000000
iloveyou
1234567
1234
12345678
dragon
123456789
sunshine
princess
654321
superman
qazwsx
michael
Football
baseball
liverpool
jordan23
slipknot
batman
trustno1
EOF
        
        chown "$REAL_USER:$REAL_USER" wordlists/common-passwords.txt
        print_success "Basic wordlist created: wordlists/common-passwords.txt"
    fi
    
    # Check for Docker Compose file
    if [[ -f "docker-compose.simple.yml" ]]; then
        print_success "Docker Compose configuration found"
    elif [[ -f "webapp/docker-compose.yml" ]]; then
        print_success "Docker Compose configuration found in webapp/"
    else
        print_error "Docker Compose configuration not found"
        print_info "Expected files: docker-compose.simple.yml or webapp/docker-compose.yml"
        exit 1
    fi
}

# Determine which Docker Compose command to use
get_compose_command() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
    else
        print_error "No Docker Compose command available"
        exit 1
    fi
}

# Start HashWrap services
start_hashwrap() {
    print_step "Starting HashWrap services"
    
    local compose_cmd
    compose_cmd=$(get_compose_command)
    
    # Determine compose file to use
    local compose_file=""
    if [[ -f "docker-compose.simple.yml" ]]; then
        compose_file="-f docker-compose.simple.yml"
    elif [[ -f "webapp/docker-compose.yml" ]]; then
        cd webapp
        compose_file="-f docker-compose.yml"
    fi
    
    # Build and start services
    print_info "Building containers..."
    $compose_cmd $compose_file build --no-cache
    
    print_info "Starting services..."
    $compose_cmd $compose_file up -d
    
    print_success "HashWrap services started"
}

# Wait for services to become ready
wait_for_services() {
    print_step "Waiting for services to become ready"
    
    local max_attempts=30
    local attempt=1
    local service_url="http://localhost:5000"
    
    if [[ -f "webapp/docker-compose.yml" ]]; then
        service_url="http://localhost:8000"  # Adjust if webapp uses different port
    fi
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -o /dev/null -w "%{http_code}" "$service_url/login" 2>/dev/null | grep -q "200\|302"; then
            print_success "HashWrap is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    print_error "Services did not become ready within expected time"
    print_info "Check service logs for issues"
    return 1
}

# Display completion information
show_completion_info() {
    local service_url="http://localhost:5000"
    local compose_cmd
    compose_cmd=$(get_compose_command)
    
    # Adjust URL based on compose file
    if [[ -f "webapp/docker-compose.yml" ]]; then
        service_url="http://localhost:8000"
    fi
    
    echo ""
    print_success "HashWrap installation completed successfully!"
    echo ""
    echo -e "${GREEN}${BOLD}🌐 Access Information:${NC}"
    echo -e "   Web Interface: ${BLUE}$service_url${NC}"
    echo -e "   Default Login: ${BLUE}admin / admin${NC}"
    echo ""
    echo -e "${GREEN}${BOLD}📝 Next Steps:${NC}"
    echo -e "   1. Open $service_url in your browser"
    echo -e "   2. Login with admin/admin credentials"
    echo -e "   3. Upload your hash files for cracking"
    echo -e "   4. Monitor job progress in the dashboard"
    echo ""
    echo -e "${GREEN}${BOLD}🔧 Management Commands:${NC}"
    
    if [[ -f "docker-compose.simple.yml" ]]; then
        echo -e "   • View logs:     ${BLUE}$compose_cmd -f docker-compose.simple.yml logs -f${NC}"
        echo -e "   • Stop services: ${BLUE}$compose_cmd -f docker-compose.simple.yml down${NC}"
        echo -e "   • Restart:       ${BLUE}$compose_cmd -f docker-compose.simple.yml restart${NC}"
    else
        echo -e "   • View logs:     ${BLUE}cd webapp && $compose_cmd logs -f${NC}"
        echo -e "   • Stop services: ${BLUE}cd webapp && $compose_cmd down${NC}"
        echo -e "   • Restart:       ${BLUE}cd webapp && $compose_cmd restart${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}${BOLD}📁 Important Directories:${NC}"
    echo -e "   • Upload files:  ${BLUE}./data/uploads/${NC}"
    echo -e "   • Results:       ${BLUE}./data/results/${NC}"  
    echo -e "   • Wordlists:     ${BLUE}./wordlists/${NC}"
    echo -e "   • Logs:          ${BLUE}./setup.log${NC}"
    echo ""
    
    # Show GPU status
    if docker info 2>/dev/null | grep -q nvidia; then
        print_success "🚀 GPU acceleration is enabled for faster cracking!"
        
        # Show available GPUs
        if command -v nvidia-smi >/dev/null 2>&1; then
            echo -e "${GREEN}${BOLD}🎮 Available GPUs:${NC}"
            nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | \
                sed 's/^/   • /' | sed 's/, / - /' | sed 's/$/ MB/'
        fi
    else
        print_warning "💡 For GPU acceleration, ensure NVIDIA drivers and Container Toolkit are installed"
    fi
    
    echo ""
    echo -e "${YELLOW}${BOLD}⚠️  Security Reminders:${NC}"
    echo -e "   • Change default admin password immediately"
    echo -e "   • Use only for authorized penetration testing"
    echo -e "   • Monitor resource usage during intensive cracking"
    echo -e "   • Regularly update wordlists for better results"
    echo ""
    
    # Docker group warning
    if groups "$REAL_USER" | grep -q docker; then
        if [[ $EUID -eq 0 && -n "${SUDO_USER:-}" ]]; then
            print_warning "You may need to log out and back in for Docker group permissions to take effect"
        fi
    fi
}

# Cleanup function for errors
cleanup_on_error() {
    print_error "Installation failed. Cleaning up..."
    
    # Stop any running containers
    local compose_cmd
    if compose_cmd=$(get_compose_command 2>/dev/null); then
        if [[ -f "docker-compose.simple.yml" ]]; then
            $compose_cmd -f docker-compose.simple.yml down 2>/dev/null || true
        elif [[ -f "webapp/docker-compose.yml" ]]; then
            cd webapp && $compose_cmd down 2>/dev/null || true
        fi
    fi
    
    print_info "Check $LOG_FILE for detailed error information"
    exit 1
}

# Main installation function
main() {
    # Set up error handling
    trap cleanup_on_error ERR
    
    print_header
    
    # Check if user wants help
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --gpu-check)
            check_gpu_support
            exit 0
            ;;
        --clean)
            clean_installation
            exit 0
            ;;
    esac
    
    # Run installation steps
    detect_os
    check_root
    check_system_requirements
    install_docker
    install_docker_compose
    install_nvidia_support
    setup_application
    start_hashwrap
    
    if wait_for_services; then
        show_completion_info
        print_success "Setup completed successfully!"
    else
        print_error "Services failed to start properly"
        print_info "Check logs: $(get_compose_command) logs"
        exit 1
    fi
}

# Help function
show_help() {
    echo "HashWrap Setup Script"
    echo ""
    echo "USAGE:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --help, -h     Show this help message"
    echo "  --gpu-check    Check GPU availability and drivers"
    echo "  --clean        Stop services and clean up containers"
    echo ""
    echo "DESCRIPTION:"
    echo "  This script automatically installs Docker, Docker Compose, and sets up"
    echo "  HashWrap for penetration testing hash cracking operations."
    echo ""
    echo "REQUIREMENTS:"
    echo "  • Linux system (Ubuntu, Debian, RHEL, CentOS, Fedora, Arch)"
    echo "  • 2GB+ RAM (4GB+ recommended)"
    echo "  • 5GB+ disk space"
    echo "  • Internet connection for package downloads"
    echo "  • sudo privileges for system modifications"
    echo ""
    echo "GPU SUPPORT:"
    echo "  • NVIDIA GPU with recent drivers (optional)"
    echo "  • NVIDIA Container Toolkit (auto-installed)"
    echo ""
}

# GPU check function
check_gpu_support() {
    echo "GPU Support Check"
    echo "=================="
    
    if command -v nvidia-smi >/dev/null 2>&1; then
        print_success "NVIDIA drivers installed"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
        
        if docker info 2>/dev/null | grep -q nvidia; then
            print_success "NVIDIA Container Toolkit configured"
            
            # Test GPU access in container
            if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi >/dev/null 2>&1; then
                print_success "GPU access in containers: OK"
            else
                print_warning "GPU access in containers: FAILED"
            fi
        else
            print_warning "NVIDIA Container Toolkit not configured"
            print_info "Run setup script to install Container Toolkit"
        fi
    else
        print_warning "NVIDIA drivers not found"
        print_info "Install NVIDIA drivers for GPU acceleration"
    fi
    
    if command -v lspci >/dev/null 2>&1; then
        echo ""
        echo "Available GPUs:"
        lspci | grep -i vga
        lspci | grep -i nvidia
    fi
}

# Clean installation function
clean_installation() {
    print_info "Cleaning up HashWrap installation"
    
    local compose_cmd
    if compose_cmd=$(get_compose_command 2>/dev/null); then
        if [[ -f "docker-compose.simple.yml" ]]; then
            print_info "Stopping simple compose services"
            $compose_cmd -f docker-compose.simple.yml down -v
        fi
        
        if [[ -f "webapp/docker-compose.yml" ]]; then
            print_info "Stopping webapp compose services"
            cd webapp && $compose_cmd down -v
        fi
    fi
    
    # Remove containers and images
    print_info "Cleaning up Docker containers and images"
    docker system prune -af || true
    
    print_success "Cleanup completed"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi