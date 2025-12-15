pipeline {
    agent any

    parameters {
        string(name: 'TAG', defaultValue: '', description: '배포할 Git 태그 (예: v0.1.0)')
        string(name: 'DEPLOY_HOST', defaultValue: '', description: '배포 대상 VM IP/도메인 (예: 10.0.0.12)')
        booleanParam(name: 'RUN_SMOKE', defaultValue: false, description: '배포 후 스모크 체크 실행 여부')
    }

    environment {
        HARBOR_REPO    = 'linkyboard/linkyboard-ai'
        LOCAL_IMAGE    = 'linkyboard-ai'

        CONTAINER_NAME = 'linkyboard-ai'

        APP_PORT       = '8000'
        HOST_PORT      = '8000'

        ENV_FILE       = '/opt/linkyboard-ai/.env.production'
        HEALTH_URL     = 'http://127.0.0.1:8000/health'

        RESOLVED_TAG   = "${params.TAG}"
        TARGET_HOST    = "${params.DEPLOY_HOST}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git fetch --tags --force'
            }
        }

        stage('Resolve Tag') {
            steps {
                script {
                    if (!params.TAG?.trim()) {
                        error('TAG 파라미터는 필수입니다. 예: v0.1.0')
                    }
                    if (!params.DEPLOY_HOST?.trim()) {
                        error('DEPLOY_HOST 파라미터는 필수입니다. 예: 10.0.0.12')
                    }
                    sh "git checkout ${params.TAG}"
                }
            }
        }

        stage('Diagnose Harbor URL Shape') {
            steps {
                withCredentials([string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL')]) {
                    sh '''
                        set -e
                        if echo "$HARBOR_URL" | grep -Eq '^(https?://|/)'; then
                          echo "HARBOR_URL 형식이 Docker login에 부적합합니다. IP[:PORT] 형태여야 합니다."
                          exit 1
                        fi
                    '''
                }
            }
        }

        stage('Docker Availability') {
            steps {
                sh 'docker version'
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    set -e
                    COMMIT=$(git rev-parse --short HEAD)
                    echo "COMMIT=$COMMIT"
                    echo "TAG=${RESOLVED_TAG}"
                    docker build -t ${LOCAL_IMAGE}:${RESOLVED_TAG} -t ${LOCAL_IMAGE}:sha-${COMMIT} .
                '''
            }
        }

        stage('Push to Harbor') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'harbor-jenkins-bot',
                        usernameVariable: 'H_USER',
                        passwordVariable: 'H_PASS'
                    ),
                    string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL')
                ]) {
                    sh '''
                        set -e
                        COMMIT=$(git rev-parse --short HEAD)
                        IMAGE="${HARBOR_URL}/${HARBOR_REPO}"

                        echo "$H_PASS" | docker login "$HARBOR_URL" --username "$H_USER" --password-stdin

                        docker tag ${LOCAL_IMAGE}:${RESOLVED_TAG} ${IMAGE}:${RESOLVED_TAG}
                        docker tag ${LOCAL_IMAGE}:sha-${COMMIT} ${IMAGE}:sha-${COMMIT}

                        docker push ${IMAGE}:${RESOLVED_TAG}
                        docker push ${IMAGE}:sha-${COMMIT}

                        docker logout "$HARBOR_URL"
                    '''
                }
            }
        }

        stage('Sign Image') {
            steps {
                withCredentials([
                    file(credentialsId: 'cosign-key', variable: 'COSIGN_KEY_FILE'),
                    string(credentialsId: 'cosign-password', variable: 'COSIGN_PASSWORD'),
                    usernamePassword(
                        credentialsId: 'harbor-jenkins-bot',
                        usernameVariable: 'ROBOT_USER',
                        passwordVariable: 'ROBOT_PASS'
                    ),
                    string(credentialsId: 'harbor-ip', variable: 'HARBOR_REGISTRY')
                ]) {
                    sh '''
                        set -e

                        if ! command -v cosign >/dev/null 2>&1; then
                            if [ ! -f ./cosign ]; then
                                wget -q "https://github.com/sigstore/cosign/releases/download/v2.2.1/cosign-linux-amd64" -O cosign
                                chmod +x cosign
                            fi
                            COSIGN_BIN=./cosign
                        else
                            COSIGN_BIN=cosign
                        fi

                        IMAGE="${HARBOR_REGISTRY}/${HARBOR_REPO}:${RESOLVED_TAG}"

                        $COSIGN_BIN login "$HARBOR_REGISTRY" -u "$ROBOT_USER" -p "$ROBOT_PASS"

                        COSIGN_PASSWORD="$COSIGN_PASSWORD" \
                        $COSIGN_BIN sign -y \
                          --key "$COSIGN_KEY_FILE" \
                          --allow-insecure-registry \
                          "$IMAGE"
                    '''
                }
            }
        }

        stage('Deploy to Remote VM (SSH)') {
            steps {
                withCredentials([
                    usernamePassword(credentialsId: 'harbor-jenkins-bot', usernameVariable: 'H_USER', passwordVariable: 'H_PASS'),
                    string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL'),
                    sshUserPrivateKey(credentialsId: 'deploy-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER')
                ]) {
                    sh """
                        set -e

                        ssh -o StrictHostKeyChecking=no -i \$SSH_KEY \$SSH_USER@${TARGET_HOST} <<'ENDSSH'
                            set -e

                            printf '%s\\n' '${H_PASS}' | docker login ${HARBOR_URL} -u '${H_USER}' --password-stdin
                            docker pull ${HARBOR_URL}/${HARBOR_REPO}:${RESOLVED_TAG}
                            docker logout ${HARBOR_URL}

                            if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
                              docker stop ${CONTAINER_NAME} || true
                              docker rm ${CONTAINER_NAME} || true
                            fi

                            if [ ! -f "${ENV_FILE}" ]; then
                              echo "ENV_FILE not found: ${ENV_FILE}"
                              exit 1
                            fi

                            docker run -d \
                              --name ${CONTAINER_NAME} \
                              --restart unless-stopped \
                              --env-file ${ENV_FILE} \
                              -p ${HOST_PORT}:${APP_PORT} \
                              ${HARBOR_URL}/${HARBOR_REPO}:${RESOLVED_TAG}
ENDSSH
                    """
                }
            }
        }


        stage('Smoke Check (Remote)') {
            when { expression { return params.RUN_SMOKE } }
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER')
                ]) {
                    sh '''
                        set -e
                        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@${TARGET_HOST}" \
                        HEALTH_URL="$HEALTH_URL" \
                        CONTAINER_NAME="$CONTAINER_NAME" \
                        bash -s << 'EOF'
                          set -e
                          echo "Health check: $HEALTH_URL"
                          for i in $(seq 1 30); do
                            if curl -fsS "$HEALTH_URL" >/dev/null; then
                              echo "Health check OK"
                              exit 0
                            fi
                            sleep 1
                          done
                          echo "Health check failed"
                          docker logs --tail 200 "$CONTAINER_NAME" || true
                          exit 1
EOF
                    '''
                }
            }
        }
    }

    post {
        success {
            withCredentials([
                string(credentialsId: 'discord-ai-success-webhook-url', variable: 'DISCORD_URL')
            ]) {
                script {
                    def payload = """
                    {
                        "username": "LinkyBoard AI CD",
                        "embeds": [{
                            "title": "🎁 AI 서버 배포 완료",
                            "color": 3066993,
                            "fields": [
                                {"name": "Version", "value": "${RESOLVED_TAG}", "inline": true},
                                {"name": "Server IP", "value": "${TARGET_HOST}", "inline": true},
                                {"name": "Status", "value": "Service Updated", "inline": false}
                            ]
                        }]
                    }
                    """
                    sh "curl -H 'Content-Type: application/json' -X POST -d '${payload}' ${DISCORD_URL}"
                }
            }
        }
        failure {
            withCredentials([
                string(credentialsId: 'discord-ai-failure-webhook-url', variable: 'DISCORD_URL')
            ]) {
                script {
                    def payload = """
                    {
                        "username": "LinkyBoard AI CD",
                        "embeds": [{
                            "title": "❌ AI 서버 배포 실패",
                            "color": 15158332,
                            "fields": [
                                {"name": "Version", "value": "${RESOLVED_TAG}", "inline": true},
                                {"name": "Server IP", "value": "${TARGET_HOST}", "inline": true},
                                {"name": "Status", "value": "Deployment Failed", "inline": false},
                                {"name": "Build URL", "value": "${BUILD_URL}", "inline": false}
                            ]
                        }]
                    }
                    """
                    sh "curl -H 'Content-Type: application/json' -X POST -d '${payload}' ${DISCORD_URL}"
                }
            }
        }
    }
}
