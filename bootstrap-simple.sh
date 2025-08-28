#!/bin/bash

# HashWrap Simple Bootstrap
# One-command setup for penetration testers

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}"
echo "=================================="
echo "   HashWrap - Pentest Edition"
echo "   Simple Hash Cracking Setup"
echo "=================================="
echo -e "${NC}"

# Check requirements
echo -e "${YELLOW}Checking requirements...${NC}"

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker requirements met${NC}"

# Check for GPU support
if docker info 2>/dev/null | grep -q nvidia; then
    echo -e "${GREEN}✅ NVIDIA GPU support detected${NC}"
    GPU_SUPPORT=true
else
    echo -e "${YELLOW}⚠️ No GPU support detected. Hashcat will run on CPU only.${NC}"
    GPU_SUPPORT=false
fi

# Create data directories
echo -e "${YELLOW}Setting up directories...${NC}"
mkdir -p data/uploads data/results wordlists

# Create basic wordlist if none exists
if [ ! -f "wordlists/common-passwords.txt" ]; then
    echo -e "${YELLOW}Creating basic wordlist...${NC}"
    cat > wordlists/common-passwords.txt << EOF
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
EOF
    echo -e "${GREEN}✅ Basic wordlist created${NC}"
fi

# Build and start
echo -e "${YELLOW}Building and starting HashWrap...${NC}"

if [ "$GPU_SUPPORT" = true ]; then
    docker-compose -f docker-compose.simple.yml up --build -d
else
    # Run without GPU support
    COMPOSE_FILE_CONTENT=$(cat docker-compose.simple.yml | grep -v "CUDA_VISIBLE_DEVICES\|NVIDIA_VISIBLE_DEVICES\|devices:" | grep -v "driver: nvidia" | grep -v "count: all" | grep -v "capabilities:")
    echo "$COMPOSE_FILE_CONTENT" | docker-compose -f - up --build -d
fi

# Wait for service to be ready
echo -e "${YELLOW}Waiting for HashWrap to start...${NC}"
sleep 10

# Check if service is running
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login | grep -q "200\|302"; then
    echo -e "${GREEN}✅ HashWrap is running!${NC}"
    echo ""
    echo -e "${GREEN}🌐 Access HashWrap at: http://localhost:5000${NC}"
    echo -e "${GREEN}👤 Default login: admin / admin${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Open http://localhost:5000 in your browser"
    echo "2. Login with admin/admin"
    echo "3. Upload your hash files"
    echo "4. Start cracking!"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "• View logs: docker-compose -f docker-compose.simple.yml logs -f"
    echo "• Stop: docker-compose -f docker-compose.simple.yml down"
    echo "• Add wordlists to: ./wordlists/"
    echo ""
    
    if [ "$GPU_SUPPORT" = true ]; then
        echo -e "${GREEN}🚀 GPU acceleration enabled for faster cracking!${NC}"
    else
        echo -e "${YELLOW}💡 For GPU acceleration, install NVIDIA Container Toolkit${NC}"
    fi
    
else
    echo -e "${RED}❌ HashWrap failed to start. Check logs:${NC}"
    echo "docker-compose -f docker-compose.simple.yml logs"
    exit 1
fi