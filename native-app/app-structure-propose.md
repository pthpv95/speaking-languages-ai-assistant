native-app/
├── app/                          # Expo Router (file-based routing)
│   ├── (auth)/                   # Route group: auth screens
│   │   ├── login.tsx
│   │   └── register.tsx
│   ├── (tabs)/                   # Route group: tab navigation
│   │   ├── _layout.tsx
│   │   ├── index.tsx
│   │   └── profile.tsx
│   ├── _layout.tsx               # Root layout
│   └── +not-found.tsx
│
├── src/                          # All non-routing source code
│   ├── components/
│   │   ├── ui/                   # Generic, reusable UI primitives
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   └── Modal.tsx
│   │   └── features/             # Feature-specific components
│   │       ├── auth/
│   │       └── dashboard/
│   │
│   ├── hooks/                    # Custom React hooks
│   │   ├── useAuth.ts
│   │   └── useTheme.ts
│   │
│   ├── stores/                   # State management (Zustand, Redux, etc.)
│   │   ├── authStore.ts
│   │   └── appStore.ts
│   │
│   ├── services/                 # API calls & external integrations
│   │   ├── api.ts                # Axios/fetch base config
│   │   ├── authService.ts
│   │   └── userService.ts
│   │
│   ├── utils/                    # Pure helper functions
│   │   ├── formatDate.ts
│   │   └── validators.ts
│   │
│   ├── constants/                # App-wide constants
│   │   ├── colors.ts
│   │   ├── spacing.ts
│   │   └── config.ts
│   │
│   ├── types/                    # TypeScript interfaces & types
│   │   ├── api.types.ts
│   │   └── user.types.ts
│   │
│   └── theme/                    # Theming system
│       ├── index.ts
│       └── darkTheme.ts
│
├── assets/                       # Static assets
│   ├── fonts/
│   ├── images/
│   └── icons/
│
├── .env                          # Environment variables
├── .env.example
├── app.json                      # Expo config
├── babel.config.js
├── tsconfig.json
└── package.json


1. Use Expo Router (file-based routing)

All screens live in app/ — the filename IS the route
Use route groups (groupName)/ to organize without affecting the URL
Keep _layout.tsx files for shared navigation wrappers

2. Separate routing from logic

app/ = only routing/screens (thin layer)
src/ = all business logic, components, hooks, services