FROM node:24-alpine

WORKDIR /app
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
