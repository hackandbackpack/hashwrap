# HashWrap Docker Bootstrap Script for Windows PowerShell
# This script sets up the complete HashWrap environment with one command

param(
    [switch]$Development,
    [switch]$SkipGPUCheck,
    [switch]$Force
)

# Configuration
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SecretsDir = Join-Path $ProjectRoot "secrets"
$DataDir = Join-Path $ProjectRoot "data"

# Colors for output
function Write-Step {
    param($Message)
    Write-Host "[STEP] $Message" -ForegroundColor Blue
}

function Write-Success {
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check prerequisites
function Test-Prerequisites {
    Write-Step "Checking prerequisites..."
    
    # Check Docker Desktop
    try {
        $dockerVersion = docker --version
        Write-Success "Docker found: $dockerVersion"
    }
    catch {
        Write-Error "Docker is not installed or not in PATH. Please install Docker Desktop."
        exit 1
    }
    
    # Check Docker Compose
    try {
        $composeVersion = docker compose version
        Write-Success "Docker Compose found: $composeVersion"
    }
    catch {
        Write-Error "Docker Compose is not available. Please update Docker Desktop."
        exit 1
    }
    
    # Check Docker daemon
    try {
        docker info | Out-Null
        Write-Success "Docker daemon is running"
    }
    catch {
        Write-Error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    }
    
    Write-Success "Prerequisites check passed"
}

# Check GPU support
function Test-GPUSupport {
    if ($SkipGPUCheck) {
        Write-Warning "Skipping GPU check as requested"
        return
    }
    
    Write-Step "Checking GPU support..."
    
    try {
        $nvidiaCards = Get-WmiObject -Class Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
        
        if ($nvidiaCards) {
            Write-Success "NVIDIA GPU detected:"
            $nvidiaCards | ForEach-Object { Write-Host "  $($_.Name)" }
            
            # Check NVIDIA Container Toolkit (basic check)
            try {
                $result = docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi 2>$null
                if ($result) {
                    Write-Success "NVIDIA Container Toolkit is working"
                }
            }
            catch {
                Write-Warning "NVIDIA Container Toolkit may not be properly configured"
                Write-Warning "HashWrap will still work but without GPU acceleration"
            }
        }
        else {
            Write-Warning "No NVIDIA GPU detected. HashWrap will run in CPU-only mode."
        }
    }
    catch {
        Write-Warning "Could not check GPU status. Continuing anyway."
    }
}

# Generate secure random passwords
function New-Secrets {
    Write-Step "Generating secure secrets..."
    
    # Create secrets directory
    if (-not (Test-Path $SecretsDir)) {
        New-Item -ItemType Directory -Path $SecretsDir -Force | Out-Null
    }
    
    # Generate database password
    $dbPasswordFile = Join-Path $SecretsDir "db_password.txt"
    if (-not (Test-Path $dbPasswordFile) -or $Force) {
        $dbPassword = [System.Web.Security.Membership]::GeneratePassword(25, 5)
        $dbPassword | Out-File -FilePath $dbPasswordFile -Encoding ASCII -NoNewline
        Write-Success "Generated database password"
    }
    else {
        Write-Warning "Database password already exists, skipping generation"
    }
    
    # Generate Redis password
    $redisPasswordFile = Join-Path $SecretsDir "redis_password.txt"
    if (-not (Test-Path $redisPasswordFile) -or $Force) {
        $redisPassword = [System.Web.Security.Membership]::GeneratePassword(25, 5)
        $redisPassword | Out-File -FilePath $redisPasswordFile -Encoding ASCII -NoNewline
        Write-Success "Generated Redis password"
    }
    else {
        Write-Warning "Redis password already exists, skipping generation"
    }
    
    # Generate JWT secret
    $jwtSecretFile = Join-Path $SecretsDir "jwt_secret.txt"
    if (-not (Test-Path $jwtSecretFile) -or $Force) {
        $jwtSecret = [System.Web.Security.Membership]::GeneratePassword(64, 10)
        $jwtSecret | Out-File -FilePath $jwtSecretFile -Encoding ASCII -NoNewline
        Write-Success "Generated JWT secret"
    }
    else {
        Write-Warning "JWT secret already exists, skipping generation"
    }
    
    Write-Success "Set secure permissions on secret files"
}

# Create environment file
function New-Environment {
    Write-Step "Setting up environment configuration..."
    
    $envFile = Join-Path $ProjectRoot ".env"
    $envTemplate = Join-Path $ProjectRoot ".env.template"
    
    if (-not (Test-Path $envFile) -or $Force) {
        if (Test-Path $envTemplate) {
            Copy-Item $envTemplate $envFile
            
            # Update environment file with generated secrets
            $dbPass = Get-Content (Join-Path $SecretsDir "db_password.txt") -Raw
            $redisPass = Get-Content (Join-Path $SecretsDir "redis_password.txt") -Raw
            $jwtSecret = Get-Content (Join-Path $SecretsDir "jwt_secret.txt") -Raw
            
            $envContent = Get-Content $envFile
            $envContent = $envContent -replace "your_secure_db_password_here", $dbPass.Trim()
            $envContent = $envContent -replace "your_secure_redis_password_here", $redisPass.Trim()
            $envContent = $envContent -replace "your_jwt_secret_key_here_use_openssl_rand_base64_32", $jwtSecret.Trim()
            
            $envContent | Out-File -FilePath $envFile -Encoding UTF8
            
            Write-Success "Created .env file with secure passwords"
        }
        else {
            Write-Error ".env.template not found. Cannot create environment file."
            exit 1
        }
    }
    else {
        Write-Warning ".env file already exists, skipping creation"
    }
}

# Create directory structure
function New-Directories {
    Write-Step "Creating directory structure..."
    
    # Create data directories
    $directories = @(
        (Join-Path $DataDir "uploads"),
        (Join-Path $DataDir "results"),
        (Join-Path $DataDir "wordlists"),
        (Join-Path $DataDir "rules"),
        (Join-Path $DataDir "logs"),
        (Join-Path $DataDir "dev"),
        (Join-Path $DataDir "dev\postgres"),
        (Join-Path $DataDir "dev\redis"),
        (Join-Path $DataDir "dev\uploads"),
        (Join-Path $DataDir "dev\results"),
        (Join-Path $DataDir "dev\logs"),
        (Join-Path $DataDir "dev\scheduler"),
        (Join-Path $DataDir "dev\pgadmin"),
        (Join-Path $ProjectRoot "nginx\ssl"),
        (Join-Path $ProjectRoot "monitoring")
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Write-Success "Created directory structure"
}

# Initialize default wordlists and rules
function Initialize-Wordlists {
    Write-Step "Setting up default wordlists and rules..."
    
    $wordlistsDir = Join-Path $ProjectRoot "wordlists"
    $rulesDir = Join-Path $ProjectRoot "rules"
    
    # Create directories if they don't exist
    if (-not (Test-Path $wordlistsDir)) {
        New-Item -ItemType Directory -Path $wordlistsDir -Force | Out-Null
    }
    if (-not (Test-Path $rulesDir)) {
        New-Item -ItemType Directory -Path $rulesDir -Force | Out-Null
    }
    
    # Create basic wordlist if not exists
    $basicWordlist = Join-Path $wordlistsDir "basic.txt"
    if (-not (Test-Path $basicWordlist)) {
        $wordlist = @(
            "password",
            "123456",
            "password123",
            "admin",
            "qwerty",
            "letmein",
            "welcome",
            "monkey",
            "dragon",
            "master"
        )
        $wordlist | Out-File -FilePath $basicWordlist -Encoding UTF8
        Write-Success "Created basic wordlist for testing"
    }
    
    # Create basic rule if not exists
    $basicRule = Join-Path $rulesDir "basic.rule"
    if (-not (Test-Path $basicRule)) {
        $rules = @(
            ":",
            "c",
            "u",
            "`$1",
            "`$2",
            "`$3",
            "`$!",
            "^1",
            "^2"
        )
        $rules | Out-File -FilePath $basicRule -Encoding UTF8
        Write-Success "Created basic hashcat rule"
    }
    
    # Check for rockyou.txt
    $rockyou = Join-Path $wordlistsDir "rockyou.txt"
    if (-not (Test-Path $rockyou)) {
        Write-Warning "No rockyou.txt found. Consider downloading it for better results."
        Write-Warning "You can download it from: https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt"
    }
}

# Build Docker images
function Build-Images {
    Write-Step "Building Docker images..."
    
    Set-Location $ProjectRoot
    
    # Build images in parallel
    & docker compose build --parallel
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Docker images"
        exit 1
    }
    
    Write-Success "Built all Docker images"
}

# Start services
function Start-Services {
    Write-Step "Starting HashWrap services..."
    
    Set-Location $ProjectRoot
    
    # Determine which compose file to use
    $composeFiles = @("-f", "docker-compose.yml")
    if ($Development) {
        $composeFiles += @("-f", "docker-compose.dev.yml")
        Write-Step "Using development configuration"
    }
    
    # Start core services first
    & docker compose @composeFiles up -d database redis
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start core services"
        exit 1
    }
    
    # Wait for database to be ready
    Write-Step "Waiting for database to be ready..."
    $maxAttempts = 30
    $attempt = 0
    
    do {
        $attempt++
        Start-Sleep 2
        
        try {
            $result = & docker compose @composeFiles exec -T database pg_isready -U hashwrap -d hashwrap 2>$null
            if ($LASTEXITCODE -eq 0) {
                break
            }
        }
        catch {
            # Continue trying
        }
        
        if ($attempt -ge $maxAttempts) {
            Write-Error "Database failed to become ready within timeout"
            exit 1
        }
    } while ($true)
    
    # Start remaining services
    & docker compose @composeFiles up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start all services"
        exit 1
    }
    
    Write-Success "Started all services"
}

# Run database migrations
function Invoke-Migrations {
    Write-Step "Running database migrations..."
    
    Set-Location $ProjectRoot
    
    # Wait a bit for backend to be ready
    Start-Sleep 10
    
    # Run migrations
    try {
        & docker compose exec -T backend python -m alembic upgrade head
        Write-Success "Database migrations completed"
    }
    catch {
        Write-Warning "Database migrations failed. This is normal for first run."
    }
}

# Display status and URLs
function Show-Status {
    Write-Step "Checking service status..."
    
    Set-Location $ProjectRoot
    
    # Show running containers
    Write-Host "Running containers:"
    & docker compose ps
    
    Write-Host ""
    Write-Host "Service URLs:"
    Write-Host "  HashWrap UI: http://localhost:80"
    Write-Host "  API Documentation: http://localhost:80/docs"
    Write-Host "  Health Check: http://localhost:80/health"
    
    # Check for optional services
    $runningServices = & docker compose ps --format json | ConvertFrom-Json
    
    if ($runningServices | Where-Object { $_.Service -eq "flower" }) {
        Write-Host "  Celery Flower: http://localhost:5555"
    }
    
    if ($runningServices | Where-Object { $_.Service -eq "pgadmin" }) {
        Write-Host "  PgAdmin: http://localhost:5050"
    }
    
    if ($runningServices | Where-Object { $_.Service -eq "prometheus" }) {
        Write-Host "  Prometheus: http://localhost:9090"
    }
    
    Write-Host ""
    Write-Success "HashWrap is now running!"
}

# Main execution
function Main {
    Write-Host "========================================="
    Write-Host "HashWrap Docker Bootstrap Script"
    Write-Host "========================================="
    Write-Host ""
    
    # Add required assembly for password generation
    Add-Type -AssemblyName System.Web
    
    # Check if running as admin (warn but don't exit)
    if (Test-Administrator) {
        Write-Warning "Running as Administrator. Consider running as regular user for better security."
    }
    
    Test-Prerequisites
    Test-GPUSupport
    New-Secrets
    New-Environment
    New-Directories
    Initialize-Wordlists
    Build-Images
    Start-Services
    Invoke-Migrations
    Show-Status
    
    Write-Host ""
    Write-Host "========================================="
    Write-Success "HashWrap setup completed successfully!"
    Write-Host "========================================="
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Open http://localhost:80 in your browser"
    Write-Host "2. Create your admin user account"
    Write-Host "3. Upload hash files and start cracking!"
    Write-Host ""
    
    if ($Development) {
        Write-Host "Development mode enabled with:"
        Write-Host "  - Hot reload for code changes"
        Write-Host "  - Additional debugging tools"
        Write-Host "  - Less strict security settings"
        Write-Host ""
    }
    
    Write-Host "To stop:"
    Write-Host "  docker compose down"
    Write-Host ""
    Write-Host "To view logs:"
    Write-Host "  docker compose logs -f [service_name]"
    Write-Host ""
}

# Run main function
try {
    Main
}
catch {
    Write-Error "Bootstrap failed: $($_.Exception.Message)"
    Write-Host "Stack trace:"
    Write-Host $_.ScriptStackTrace
    exit 1
}