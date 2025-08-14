# CSV Viewer Architecture and Deployment

## Multi-Architecture Support

The application now supports two architectures:

1. **AMD64 (x86_64)**: Default architecture for most servers
2. **ARM64 (aarch64)**: Architecture for ARM-based devices

## Docker Compose Files

- `docker-compose.yml`: Default configuration for AMD64 architecture
- `docker-compose.arm.yml`: Configuration for ARM64 architecture

## Usage Scripts

### Building Images

```bash
# Build AMD64 images (default)
./build-production-images.sh

# Build ARM64 images
./build-production-images.sh arm

# Build and push images
./build-production-images.sh amd64 push
./build-production-images.sh arm push
```

### Managing the Application

The unified `app.sh` script provides a simple interface for managing the application:

```bash
# Start application (AMD64 by default)
./app.sh start

# Start application with ARM images
./app.sh start arm

# Start application in development mode
./app.sh start dev

# Stop application (AMD64 by default)
./app.sh stop

# Stop application with ARM images
./app.sh stop arm

# Check application status
./app.sh status

# Show help
./app.sh help
```
