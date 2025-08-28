# HashWrap Frontend

A modern React + TypeScript frontend for HashWrap, the secure hash cracking orchestrator.

## Features

- **Modern Stack**: React 18, TypeScript, Vite, Tailwind CSS
- **Authentication**: JWT-based auth with 2FA support
- **Role-Based Access**: Admin, Operator, and Viewer roles with appropriate UI restrictions
- **Real-Time Updates**: Server-Sent Events for live job status updates
- **Responsive Design**: Mobile-friendly interface with dark/light theme support
- **Security-First**: CSRF protection, XSS prevention, and secure token management
- **Professional UI**: Clean, accessible interface using Radix UI components

## Pages & Features

### Authentication
- **Login**: Email/password authentication with TOTP 2FA support
- **Setup 2FA**: QR code generation and TOTP verification
- **Legal Banner**: Authorization capture and compliance notice

### Dashboard
- **System Health**: Real-time monitoring of services and components
- **Key Metrics**: Active jobs, queue size, total cracked hashes
- **Recent Activity**: Latest job status and updates
- **Resource Monitoring**: CPU, memory, and disk usage indicators

### Upload (Admin/Operator)
- **File Upload**: Drag-and-drop interface for hash files
- **Project Management**: Create and select projects for organization
- **Hash Type Override**: Manual hash type specification
- **Upload History**: Track and manage uploaded files

### Jobs
- **Job Listing**: Complete overview of all cracking jobs
- **Status Filtering**: Filter by running, queued, completed status
- **Job Details**: Comprehensive view with events and progress
- **Job Controls**: Pause, resume, cancel operations

### Results
- **Search & Filter**: Find results by hash, password, or type
- **Role-Based Reveal**: Password reveal restricted by user permissions
- **Export Functions**: CSV and JSON export capabilities
- **Copy to Clipboard**: Easy copying of hashes and passwords

### Settings (Admin Only)
- **User Management**: Create, edit, and manage user accounts
- **Webhook Configuration**: Set up notifications for job events
- **Attack Profiles**: Manage cracking profiles and strategies

### Audit Log (Admin Only)
- **Activity Tracking**: Complete log of user actions
- **Compliance View**: Detailed audit trail for regulatory requirements
- **Filtering**: Filter by user, action, resource, or date range
- **Export Capability**: Download audit logs for external analysis

## Technology Stack

### Core
- **React 18**: Modern React with hooks and concurrent features
- **TypeScript**: Full type safety with strict configuration
- **Vite**: Fast build tool with hot module replacement
- **React Router**: Client-side routing with protected routes

### Styling
- **Tailwind CSS**: Utility-first styling with custom theme
- **Radix UI**: Accessible, unstyled UI components
- **Lucide React**: Beautiful, customizable icons
- **Custom CSS Variables**: Theme-aware color system

### State Management
- **TanStack Query**: Server state management with caching
- **React Context**: Global auth and theme state
- **React Hook Form**: Performant form handling with validation

### Data & API
- **Axios**: HTTP client with interceptors and error handling
- **Zod**: Runtime type validation for forms
- **OpenAPI Types**: Type-safe API client generation

### Development
- **ESLint**: Code linting with TypeScript rules
- **Prettier**: Code formatting
- **Vitest**: Testing framework
- **TypeScript**: Strict type checking

## Getting Started

### Prerequisites
- Node.js 18+ and npm 9+
- HashWrap backend API running

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Type checking
npm run type-check

# Linting
npm run lint
npm run lint:fix

# Formatting
npm run format
npm run format:check
```

### Environment Configuration

The frontend automatically proxies API requests to `http://localhost:8000` during development. For production, configure your web server to proxy `/api` requests to your backend.

### Build Configuration

- **Development**: Hot reload, source maps, debugging tools
- **Production**: Optimized bundle with code splitting
- **Proxy**: Automatic API proxying to backend server

## Architecture

### Directory Structure
```
src/
├── components/        # Reusable UI components
│   ├── ui/           # Base UI components
│   └── Layout.tsx    # Main application layout
├── contexts/         # React contexts for global state
├── hooks/           # Custom React hooks
├── lib/             # Utilities and API client
├── pages/           # Route components
├── types/           # TypeScript type definitions
└── main.tsx         # Application entry point
```

### Key Patterns
- **Composition**: Compose complex UI from simple components
- **Hooks**: Custom hooks for reusable logic
- **Context**: Global state without prop drilling
- **Query Keys**: Consistent cache keys for server state
- **Error Boundaries**: Graceful error handling

## Security Features

### Authentication
- JWT token management with secure storage
- Automatic token refresh and expiry handling
- TOTP-based two-factor authentication
- Session cleanup on logout

### Authorization
- Role-based route protection
- Component-level permission checks
- API request authentication headers
- Unauthorized access handling

### Data Protection
- XSS prevention through React's built-in protection
- CSRF protection via custom headers
- Secure password reveal mechanics
- Input validation and sanitization

### Privacy
- Legal banner and authorization capture
- Audit trail for compliance
- No sensitive data in logs
- Secure token storage practices

## API Integration

The frontend uses a type-safe API client with:

- **Automatic Authentication**: JWT tokens in request headers
- **Error Handling**: Consistent error processing and user feedback
- **Response Caching**: Intelligent caching with TanStack Query
- **Request Retry**: Automatic retry for transient failures
- **TypeScript Types**: Full type safety for API responses

## Real-Time Features

### Server-Sent Events
- Live job status updates
- System health monitoring
- Real-time progress indicators
- Automatic reconnection handling

### Optimistic Updates
- Immediate UI feedback
- Automatic rollback on errors
- Consistent state management
- Enhanced user experience

## Accessibility

- **WCAG Compliance**: Following web accessibility guidelines
- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Reader**: Proper ARIA labels and descriptions
- **Color Contrast**: Sufficient contrast ratios in all themes
- **Focus Management**: Clear focus indicators and management

## Performance

- **Code Splitting**: Automatic route-based code splitting
- **Bundle Optimization**: Optimized vendor and feature chunks
- **Image Optimization**: Efficient asset handling
- **Caching Strategy**: Smart caching for API responses
- **Lazy Loading**: On-demand loading of components

## Contributing

1. Follow TypeScript strict mode requirements
2. Use Prettier for code formatting
3. Write tests for new components
4. Follow existing patterns and conventions
5. Update documentation for new features

## License

Same as the main HashWrap project.