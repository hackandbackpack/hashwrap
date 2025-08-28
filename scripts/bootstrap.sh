#!/bin/bash

# HashWrap Docker Bootstrap Script
# This script sets up the complete HashWrap environment with one command

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$PROJECT_ROOT/secrets"
DATA_DIR="$PROJECT_ROOT/data"

# Functions
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root for security reasons."
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    # Check if user is in docker group
    if ! groups $USER | grep -q docker; then
        print_warning "User $USER is not in the docker group. You may need to use sudo."
    fi
    
    print_success "Prerequisites check passed"
}

# Check GPU support
check_gpu_support() {
    print_step "Checking GPU support..."
    
    if command -v nvidia-smi &> /dev/null; then
        print_success "NVIDIA GPU detected"
        nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -5
        
        # Check for nvidia-container-toolkit
        if docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
            print_success "NVIDIA Container Toolkit is working"
        else
            print_warning "NVIDIA Container Toolkit may not be properly configured"
            print_warning "HashWrap will still work but without GPU acceleration"
        fi
    else
        print_warning "No NVIDIA GPU detected. HashWrap will run in CPU-only mode."
    fi
}

# Generate secure random passwords
generate_secrets() {
    print_step "Generating secure secrets..."
    
    mkdir -p "$SECRETS_DIR"
    
    # Generate database password
    if [[ ! -f "$SECRETS_DIR/db_password.txt" ]]; then
        openssl rand -base64 32 | tr -d "=+/" | cut -c1-25 > "$SECRETS_DIR/db_password.txt"
        print_success "Generated database password"
    else
        print_warning "Database password already exists, skipping generation"
    fi
    
    # Generate Redis password
    if [[ ! -f "$SECRETS_DIR/redis_password.txt" ]]; then
        openssl rand -base64 32 | tr -d "=+/" | cut -c1-25 > "$SECRETS_DIR/redis_password.txt"
        print_success "Generated Redis password"
    else
        print_warning "Redis password already exists, skipping generation"
    fi
    
    # Generate JWT secret
    if [[ ! -f "$SECRETS_DIR/jwt_secret.txt" ]]; then
        openssl rand -base64 64 | tr -d "=+/" | cut -c1-64 > "$SECRETS_DIR/jwt_secret.txt"
        print_success "Generated JWT secret"
    else
        print_warning "JWT secret already exists, skipping generation"
    fi
    
    # Set secure permissions
    chmod 600 "$SECRETS_DIR"/*.txt
    print_success "Set secure permissions on secret files"
}

# Create environment file
create_environment() {
    print_step "Setting up environment configuration..."
    
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        if [[ -f "$PROJECT_ROOT/.env.template" ]]; then
            cp "$PROJECT_ROOT/.env.template" "$PROJECT_ROOT/.env"
            
            # Update environment file with generated secrets
            DB_PASS=$(cat "$SECRETS_DIR/db_password.txt")
            REDIS_PASS=$(cat "$SECRETS_DIR/redis_password.txt")
            JWT_SECRET=$(cat "$SECRETS_DIR/jwt_secret.txt")
            
            sed -i "s/your_secure_db_password_here/$DB_PASS/g" "$PROJECT_ROOT/.env"
            sed -i "s/your_secure_redis_password_here/$REDIS_PASS/g" "$PROJECT_ROOT/.env"
            sed -i "s/your_jwt_secret_key_here_use_openssl_rand_base64_32/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
            
            print_success "Created .env file with secure passwords"
        else
            print_error ".env.template not found. Cannot create environment file."
            exit 1
        fi
    else
        print_warning ".env file already exists, skipping creation"
    fi
}

# Create directory structure
create_directories() {
    print_step "Creating directory structure..."
    
    # Create data directories
    mkdir -p "$DATA_DIR"/{uploads,results,wordlists,rules,logs,dev}
    mkdir -p "$DATA_DIR"/dev/{postgres,redis,uploads,results,logs,scheduler,pgadmin}
    mkdir -p "$PROJECT_ROOT"/{nginx/ssl,monitoring}
    
    # Set permissions
    chmod 755 "$DATA_DIR"
    chmod 755 "$DATA_DIR"/*
    
    print_success "Created directory structure"
}

# Initialize default wordlists and rules
setup_wordlists() {
    print_step "Setting up default wordlists and rules..."
    
    # Create basic wordlist if not exists
    if [[ ! -f "$PROJECT_ROOT/wordlists/rockyou.txt" ]] && [[ ! -f "$DATA_DIR/wordlists/rockyou.txt" ]]; then
        print_warning "No rockyou.txt found. Consider downloading it for better results."
        
        # Create a basic wordlist for testing
        cat > "$PROJECT_ROOT/wordlists/basic.txt" << 'EOF'
password
123456
password123
admin
qwerty
letmein
welcome
monkey
dragon
master
EOF
        print_success "Created basic wordlist for testing"
    fi
    
    # Create basic rule if not exists
    if [[ ! -f "$PROJECT_ROOT/rules/basic.rule" ]]; then
        cat > "$PROJECT_ROOT/rules/basic.rule" << 'EOF'
:
c
u
$1
$2
$3
$!
^1
^2
EOF
        print_success "Created basic hashcat rule"
    fi
}

# Build Docker images
build_images() {
    print_step "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build images in order (dependencies first)
    docker compose build --parallel
    
    print_success "Built all Docker images"
}

# Start services
start_services() {
    print_step "Starting HashWrap services..."
    
    cd "$PROJECT_ROOT"
    
    # Start core services first
    docker compose up -d database redis
    
    # Wait for database to be ready
    print_step "Waiting for database to be ready..."
    for i in {1..30}; do
        if docker compose exec -T database pg_isready -U hashwrap -d hashwrap &> /dev/null; then
            break
        fi
        sleep 2
    done
    
    # Start remaining services
    docker compose up -d
    
    print_success "Started all services"
}

# Run database migrations
run_migrations() {
    print_step "Running database migrations..."
    
    cd "$PROJECT_ROOT"
    
    # Wait a bit for backend to be ready
    sleep 10
    
    # Run migrations
    if docker compose exec -T backend python -m alembic upgrade head; then
        print_success "Database migrations completed"
    else
        print_warning "Database migrations failed. This is normal for first run."
    fi
}

# Create initial admin user
create_admin_user() {
    print_step "Creating initial admin user..."
    
    cd "$PROJECT_ROOT"
    
    # This would typically be done via API or management command
    print_warning "Please create admin user manually via the web interface"
    print_warning "Or implement a management command in the backend"
}

# Display status and URLs
show_status() {
    print_step "Checking service status..."
    
    cd "$PROJECT_ROOT"
    
    # Show running containers
    echo "Running containers:"
    docker compose ps
    
    echo ""
    echo "Service URLs:"
    echo "  HashWrap UI: http://localhost:80"
    echo "  API Documentation: http://localhost:80/docs"
    echo "  Health Check: http://localhost:80/health"
    
    if docker compose ps | grep -q flower; then
        echo "  Celery Flower: http://localhost:5555"
    fi
    
    if docker compose ps | grep -q pgadmin; then
        echo "  PgAdmin: http://localhost:5050"
    fi
    
    if docker compose ps | grep -q prometheus; then
        echo "  Prometheus: http://localhost:9090"
    fi
    
    echo ""
    print_success "HashWrap is now running!"
}

# Main execution
main() {
    echo "========================================="
    echo "HashWrap Docker Bootstrap Script"
    echo "========================================="
    echo ""
    
    check_root
    check_prerequisites
    check_gpu_support
    generate_secrets
    create_environment
    create_directories
    setup_wordlists
    build_images
    start_services
    run_migrations
    show_status
    
    echo ""
    echo "========================================="
    print_success "HashWrap setup completed successfully!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Open http://localhost:80 in your browser"
    echo "2. Create your admin user account"
    echo "3. Upload hash files and start cracking!"
    echo ""
    echo "For development:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d"
    echo ""
    echo "To stop:"
    echo "  docker compose down"
    echo ""
    echo "To view logs:"
    echo "  docker compose logs -f [service_name]"
    echo ""
}

# Run main function
main "$@"