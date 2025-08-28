#!/bin/bash

# HashWrap Bootstrap Script
# One-command deployment for HashWrap password cracking service

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
HASHWRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="${HASHWRAP_DIR}/secrets"
DATA_DIR="${HASHWRAP_DIR}/data"
WORDLISTS_DIR="${HASHWRAP_DIR}/wordlists"
RULES_DIR="${HASHWRAP_DIR}/rules"

print_header() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "       HashWrap Bootstrap Script"
    echo "   Secure Password Cracking Service"
    echo "=========================================="
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_requirements() {
    print_info "Checking system requirements..."
    
    # Check if Docker is installed
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if NVIDIA Docker runtime is available (for GPU support)
    if docker info 2>/dev/null | grep -q nvidia; then
        print_success "NVIDIA Container Toolkit detected"
    else
        print_warning "NVIDIA Container Toolkit not detected. GPU acceleration will not be available."
        print_info "To enable GPU support, install NVIDIA Container Toolkit:"
        print_info "https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
    
    print_success "System requirements check completed"
}

generate_secrets() {
    print_info "Generating secure secrets..."
    
    mkdir -p "${SECRETS_DIR}"
    
    # Generate database password
    if [ ! -f "${SECRETS_DIR}/db_password.txt" ]; then
        openssl rand -base64 32 > "${SECRETS_DIR}/db_password.txt"
        print_success "Generated database password"
    fi
    
    # Generate Redis password
    if [ ! -f "${SECRETS_DIR}/redis_password.txt" ]; then
        openssl rand -base64 32 > "${SECRETS_DIR}/redis_password.txt"
        print_success "Generated Redis password"
    fi
    
    # Generate JWT secret
    if [ ! -f "${SECRETS_DIR}/jwt_secret.txt" ]; then
        openssl rand -base64 64 > "${SECRETS_DIR}/jwt_secret.txt"
        print_success "Generated JWT secret"
    fi
    
    # Set proper permissions on secrets
    chmod 600 "${SECRETS_DIR}"/*.txt
    print_success "Set secure permissions on secrets"
}

create_directories() {
    print_info "Creating application directories..."
    
    # Create data directories
    mkdir -p "${DATA_DIR}/uploads"
    mkdir -p "${DATA_DIR}/results"
    
    # Create wordlists directory if it doesn't exist
    if [ ! -d "${WORDLISTS_DIR}" ]; then
        mkdir -p "${WORDLISTS_DIR}"
        print_info "Created wordlists directory. Place your wordlist files here."
    fi
    
    # Create rules directory if it doesn't exist
    if [ ! -d "${RULES_DIR}" ]; then
        mkdir -p "${RULES_DIR}"
        print_info "Created rules directory. Place your hashcat rule files here."
    fi
    
    print_success "Application directories created"
}

setup_environment() {
    print_info "Setting up environment configuration..."
    
    if [ ! -f "${HASHWRAP_DIR}/.env" ]; then
        # Copy example environment file
        cp "${HASHWRAP_DIR}/.env.example" "${HASHWRAP_DIR}/.env"
        
        # Update with generated passwords
        DB_PASSWORD=$(cat "${SECRETS_DIR}/db_password.txt")
        REDIS_PASSWORD=$(cat "${SECRETS_DIR}/redis_password.txt")
        
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${DB_PASSWORD}/" "${HASHWRAP_DIR}/.env"
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" "${HASHWRAP_DIR}/.env"
        
        print_success "Environment configuration created"
    else
        print_info "Environment file already exists"
    fi
    
    # Copy example config files if they don't exist
    if [ ! -f "${HASHWRAP_DIR}/hashwrap.yaml" ]; then
        cp "${HASHWRAP_DIR}/hashwrap.example.yaml" "${HASHWRAP_DIR}/hashwrap.yaml"
        print_success "Created hashwrap.yaml configuration"
    fi
    
    if [ ! -f "${HASHWRAP_DIR}/notifiers.yaml" ]; then
        cp "${HASHWRAP_DIR}/notifiers.example.yaml" "${HASHWRAP_DIR}/notifiers.yaml"
        print_success "Created notifiers.yaml configuration"
    fi
}

download_sample_wordlists() {
    if [ ! "$(ls -A ${WORDLISTS_DIR})" ]; then
        print_info "Downloading sample wordlists..."
        
        # Create a small sample wordlist for testing
        cat > "${WORDLISTS_DIR}/common-passwords.txt" << EOF
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
EOF
        
        print_success "Created sample wordlist: common-passwords.txt"
        print_info "Add your own wordlists to ${WORDLISTS_DIR}/"
        print_info "Popular wordlists: rockyou.txt, SecLists, etc."
    fi
}

download_sample_rules() {
    if [ ! "$(ls -A ${RULES_DIR})" ]; then
        print_info "Creating sample hashcat rules..."
        
        # Create basic rules file
        cat > "${RULES_DIR}/basic.rule" << 'EOF'
:
c
u
C
t
TT
r
d
f
p
EOF
        
        print_success "Created sample rule file: basic.rule"
        print_info "Add hashcat rule files to ${RULES_DIR}/"
        print_info "Popular rules: best64.rule, d3ad0ne.rule, etc."
    fi
}

start_services() {
    print_info "Starting HashWrap services..."
    
    cd "${HASHWRAP_DIR}"
    
    # Build and start services
    docker-compose build --no-cache
    docker-compose up -d
    
    print_success "HashWrap services started"
}

wait_for_services() {
    print_info "Waiting for services to become healthy..."
    
    local max_attempts=60
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps | grep -q "Up (healthy)"; then
            if [ "$(docker-compose ps | grep -c "Up (healthy)")" -ge 3 ]; then
                print_success "Services are healthy"
                return 0
            fi
        fi
        
        echo -n "."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    print_error "Services did not become healthy within expected time"
    print_info "Check service logs: docker-compose logs"
    return 1
}

show_completion_info() {
    local frontend_url="http://localhost"
    local api_url="http://localhost/api/v1"
    
    echo ""
    print_success "HashWrap deployment completed successfully!"
    echo ""
    echo -e "${GREEN}Access Information:${NC}"
    echo -e "  🌐 Web Interface: ${BLUE}${frontend_url}${NC}"
    echo -e "  🔌 API Endpoint:  ${BLUE}${api_url}${NC}"
    echo -e "  📊 API Docs:      ${BLUE}${api_url}/docs${NC}"
    echo ""
    echo -e "${GREEN}Initial Setup:${NC}"
    echo -e "  1. Open ${BLUE}${frontend_url}${NC} in your browser"
    echo -e "  2. Create your admin account"
    echo -e "  3. Enable 2FA authentication"
    echo -e "  4. Configure notification webhooks (optional)"
    echo ""
    echo -e "${GREEN}Next Steps:${NC}"
    echo -e "  • Add wordlists to: ${WORDLISTS_DIR}/"
    echo -e "  • Add rule files to: ${RULES_DIR}/"
    echo -e "  • Configure webhooks in: notifiers.yaml"
    echo -e "  • Review security settings in: hashwrap.yaml"
    echo ""
    echo -e "${GREEN}Management Commands:${NC}"
    echo -e "  • View logs:     ${BLUE}docker-compose logs -f${NC}"
    echo -e "  • Stop services: ${BLUE}docker-compose down${NC}"
    echo -e "  • Restart:       ${BLUE}docker-compose restart${NC}"
    echo -e "  • Update:        ${BLUE}git pull && docker-compose build --no-cache && docker-compose up -d${NC}"
    echo ""
    echo -e "${YELLOW}Security Reminder:${NC}"
    echo -e "  ⚠ Use only for authorized penetration testing"
    echo -e "  ⚠ Review all jobs for proper authorization"
    echo -e "  ⚠ Regularly review audit logs"
    echo ""
}

show_gpu_info() {
    if docker info 2>/dev/null | grep -q nvidia; then
        echo ""
        print_info "GPU Information:"
        docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
        echo ""
    fi
}

main() {
    print_header
    
    check_requirements
    generate_secrets
    create_directories
    setup_environment
    download_sample_wordlists
    download_sample_rules
    start_services
    
    if wait_for_services; then
        show_gpu_info
        show_completion_info
    else
        print_error "Deployment completed with issues. Check logs for details."
        echo ""
        echo "Debug commands:"
        echo "  docker-compose logs --tail=50"
        echo "  docker-compose ps"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "HashWrap Bootstrap Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --gpu-check    Check GPU availability"
        echo "  --clean        Clean up and restart"
        echo ""
        exit 0
        ;;
    --gpu-check)
        if command -v nvidia-smi >/dev/null 2>&1; then
            nvidia-smi
        else
            print_error "nvidia-smi not found. Install NVIDIA drivers first."
        fi
        exit 0
        ;;
    --clean)
        print_info "Cleaning up existing deployment..."
        docker-compose down -v
        docker system prune -f
        print_success "Cleanup completed"
        ;;
esac

# Run main function
main "$@"