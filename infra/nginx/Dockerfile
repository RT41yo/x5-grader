FROM nginx:1.27-alpine

# Удалим дефолтный конфиг
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш кастомный конфиг
COPY default.conf /etc/nginx/conf.d/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
