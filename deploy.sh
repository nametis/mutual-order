#!/bin/bash
# deploy.sh - Mutual Order Migration Deployment Script

set -e  # Exit on any error

echo "🚀 Mutual Order Migration Deployment"
echo "======================================"

# Configuration
COMPOSE_FILE="docker-compose.mutual-order.yml"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠️  WARNING:${NC} $1"
}

error() {
    echo -e "${RED}❌ ERROR:${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}✅ SUCCESS:${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "$COMPOSE_FILE not found"
    fi
    
    if [[ ! -f ".env" ]]; then
        warn ".env file not found - using default values"
    fi
    
    success "Prerequisites check passed"
}

# Create backup
create_backup() {
    log "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup app.py if it exists
    if [[ -f "app.py" ]]; then
        cp app.py "${BACKUP_DIR}/app_${TIMESTAMP}.py"
        log "Backed up app.py"
    fi
    
    # Backup database if containers are running
    if docker-compose -f "$COMPOSE_FILE" ps db | grep -q "Up"; then
        log "Backing up database..."
        docker-compose -f "$COMPOSE_FILE" exec -T db pg_dump -U postgres mutual_order | gzip > "${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
        success "Database backed up"
    else
        warn "Database container not running - skipping database backup"
    fi
    
    success "Backup completed"
}

# Build and deploy
deploy() {
    log "Starting deployment..."
    
    # # Stop existing containers
    # log "Stopping existing containers..."
    # docker-compose -f "$COMPOSE_FILE" down
    
    # # Build new images
    # log "Building new images..."
    # docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    # # Start services
    # log "Starting services..."
    # docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 10
    
    # Check health
    check_health
    
    success "Deployment completed"
}

# Check service health
check_health() {
    log "Checking service health..."
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        local healthy=true
        
        # Check database
        if ! docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            healthy=false
        fi
        
        # Check Redis
        if ! docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping | grep -q PONG; then
            healthy=false
        fi
        
        # Check app (if accessible)
        if ! docker-compose -f "$COMPOSE_FILE" exec -T app curl -f http://localhost:5001/ > /dev/null 2>&1; then
            healthy=false
        fi
        
        if [[ "$healthy" == true ]]; then
            success "All services are healthy"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts - Services not ready yet..."
        sleep 5
        ((attempt++))
    done
    
    error "Services failed to become healthy"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    docker-compose -f "$COMPOSE_FILE" exec -T app python -c "
from app import get_app
app = get_app()
with app.app_context():
    from models import db
    db.create_all()
    print('✅ Database tables created/verified')
"
    
    success "Database initialized"
}

# Show status
show_status() {
    log "Service Status:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log "Service Logs (last 10 lines):"
    docker-compose -f "$COMPOSE_FILE" logs --tail=10
    
    echo ""
    log "Application URL: https://lomule.ddns.net"
    log "Adminer URL: http://localhost:8080 (if enabled)"
}

# Rollback function
rollback() {
    log "Rolling back to previous version..."
    
    # Stop current containers
    docker-compose -f "$COMPOSE_FILE" down
    
    # Find latest backup
    local latest_backup=$(ls -t ${BACKUP_DIR}/app_*.py 2>/dev/null | head -n1)
    
    if [[ -n "$latest_backup" ]]; then
        cp "$latest_backup" app.py
        log "Restored app.py from $latest_backup"
    else
        error "No backup found for rollback"
    fi
    
    # Restart with old code
    docker-compose -f "$COMPOSE_FILE" up --build -d
    
    success "Rollback completed"
}

# Main menu
main() {
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            create_backup
            deploy
            init_database
            show_status
            ;;
        "backup")
            create_backup
            ;;
        "health")
            check_health
            ;;
        "status")
            show_status
            ;;
        "rollback")
            rollback
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  deploy   - Full deployment (default)"
            echo "  backup   - Create backup only"
            echo "  health   - Check service health"
            echo "  status   - Show service status"
            echo "  rollback - Rollback to previous version"
            echo "  help     - Show this help"
            ;;
        *)
            error "Unknown command: $1. Use '$0 help' for usage information."
            ;;
    esac
}

# Run main function with all arguments
main "$@"