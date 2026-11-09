# 今日旧闻 — 静态站点镜像
#
# 构建：docker build -t jiuwen:latest .
# 运行：docker run -d --name jiuwen -p 8080:8080 --restart unless-stopped jiuwen:latest
#
# 说明：dist/ 在宿主机由 `python build.py` 生成（也可在 CI 里生成后再构建镜像）。
# 镜像只做静态托管，不含 Python，运行时零依赖。

FROM nginx:1.27-alpine

ENV TZ=Asia/Shanghai

COPY deploy/nginx.docker.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/

RUN rm -f /usr/share/nginx/html/index.html.bak \
    && nginx -t

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]