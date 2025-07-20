#!/bin/bash

# Local Build and Test Script for Snitch Discord Bot
# This script builds the Docker image locally and runs it with docker-compose

set -e

# Configuration
IMAGE_NAME="snitch-discord-bot"
TAG="${TAG:-latest}"
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install it first."
        exit 1
    fi
    
    if [[ ! -f ".env" ]]; then
        log_warn ".env file not found. Please copy .env.example to .env and fill in your values."
        exit 1
    fi
    
    log_info "Prerequisites check passed."
}

# Build Docker image
build_image() {
    log_info "Building Docker image: $IMAGE_NAME:$TAG"
    
    docker build -t "$IMAGE_NAME:$TAG" .
    
    log_info "Docker image built successfully."
}

# Run with docker-compose
run_compose() {
    log_info "Starting services with docker-compose..."
    
    # Stop any existing containers
    docker-compose down 2>/dev/null || true
    
    # Start services
    docker-compose up -d
    
    log_info "Services started successfully."
    log_info "Bot container: $(docker-compose ps --services | grep snitch-bot)"
    log_info "ChromaDB container: $(docker-compose ps --services | grep chroma)"
}

# Show logs
show_logs() {
    log_info "Showing container logs (press Ctrl+C to exit)..."
    docker-compose logs -f snitch-bot
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait a bit for containers to start
    sleep 10
    
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        log_info "Containers are running."
        
        # Try to check bot health endpoint (if available)
        if curl -f http://localhost:8000/health &>/dev/null; then
            log_info "Bot health check passed."
        else
            log_warn "Bot health endpoint not responding (this may be normal for Discord bots)."
        fi
        
        # Check ChromaDB
        if curl -f http://localhost:8001/api/v1/heartbeat &>/dev/null; then
            log_info "ChromaDB health check passed."
        else
            log_warn "ChromaDB health endpoint not responding."
        fi
    else
        log_error "Some containers are not running. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    docker-compose down
    log_info "Services stopped."
}

# Clean up
cleanup() {
    log_info "Cleaning up..."
    
    # Remove containers and volumes
    docker-compose down -v --remove-orphans
    
    # Remove image if requested
    read -p "Remove Docker image $IMAGE_NAME:$TAG? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi "$IMAGE_NAME:$TAG" 2>/dev/null || true
        log_info "Docker image removed."
    fi
    
    log_info "Cleanup completed."
}

# Show usage
usage() {
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  build     Build Docker image only"
    echo "  run       Build and run with docker-compose"
    echo "  logs      Show container logs"
    echo "  health    Perform health check"
    echo "  stop      Stop running services"
    echo "  clean     Clean up containers and optionally images"
    echo "  help      Show this help message"
    echo
    echo "Environment variables:"
    echo "  TAG       Docker image tag (default: latest)"
    echo
    echo "Examples:"
    echo "  $0 run              # Build and run the bot"
    echo "  TAG=v1.0 $0 build   # Build with custom tag"
    echo "  $0 logs             # Show logs"
    echo "  $0 clean            # Clean up everything"
}

# Main function
main() {
    local command="${1:-run}"
    
    case "$command" in
        "build")
            check_prerequisites
            build_image
            ;;
        "run")
            check_prerequisites
            build_image
            run_compose
            health_check
            log_info "Bot is running. Use '$0 logs' to see logs or '$0 stop' to stop."
            ;;
        "logs")
            show_logs
            ;;
        "health")
            health_check
            ;;
        "stop")
            stop_services
            ;;
        "clean")
            cleanup
            ;;
        "help"|"-h"|"--help")
            usage
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi