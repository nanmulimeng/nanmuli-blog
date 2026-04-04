# 构建阶段
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app

# 复制 Maven 配置文件
COPY pom.xml .
COPY src ./src

# 使用 Maven Wrapper 或安装 Maven
RUN apk add --no-cache maven
RUN mvn clean package -DskipTests

# 运行阶段
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# 创建上传目录
RUN mkdir -p /uploads && chmod 755 /uploads

# 从构建阶段复制 jar 文件
COPY --from=builder /app/target/*.jar app.jar

# JVM 参数优化（适合 2核2G 服务器）
ENV JAVA_OPTS="-Xms256m -Xmx512m \
    -XX:MetaspaceSize=128m \
    -XX:MaxMetaspaceSize=256m \
    -XX:+UseG1GC \
    -XX:MaxGCPauseMillis=200 \
    -XX:+HeapDumpOnOutOfMemoryError \
    -XX:HeapDumpPath=/app/heapdump.hprof"

EXPOSE 8080

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
