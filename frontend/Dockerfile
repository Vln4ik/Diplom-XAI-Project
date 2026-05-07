FROM node:22-alpine

WORKDIR /app

ENV NPM_CONFIG_REGISTRY=https://registry.npmjs.org/

COPY package.json package.json
COPY tsconfig.json tsconfig.json
COPY tsconfig.node.json tsconfig.node.json
COPY vite.config.ts vite.config.ts
COPY index.html index.html
COPY src src

RUN npm install

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
