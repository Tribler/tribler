# Tribler web UI

## Getting started

After checking out the Tribler repo, the web UI will not run out-of-the box. You'll either have to build the web UI or serve it from the Vite development server.

Building the web UI works as follows:

```
cd src/tribler/ui/
npm install
npm run build
```

This will create a `dist` folder which will automatically be served after Tribler restarts.

Alternatively, while working on the web UI, it's often more convenient use the development server:

```
cd src/tribler/ui/
rm dist -r
npm install
npm run dev
```

After restarting Tribler, requests to `/ui` will be forwarded to the development server. Tribler assumes that the development server will run at `http://localhost:5173`.