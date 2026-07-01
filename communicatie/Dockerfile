# Communicatie dashboard — productie-image
FROM node:20-bookworm-slim

WORKDIR /app

# Eerst dependencies (betere cache); pg is puur JS, geen build-tools nodig.
COPY package.json ./
RUN npm install --omit=dev

# App-code
COPY . .

ENV NODE_ENV=production
ENV PORT=3008
EXPOSE 3008

CMD ["node", "server.js"]
