FROM node:20-alpine3.18

COPY . /app
WORKDIR /app

RUN npm install

CMD ["npm", "start"]
EXPOSE 3000

# docker build -t ai-ops-frontend .
# docker run --name ai-ops-frontend -d -p 0.0.0.0:3000:3000 ai-ops-frontend