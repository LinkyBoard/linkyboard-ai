pipeline {
    agent any

    triggers {
        GenericTrigger(
            genericVariables: [
                [key: 'RELEASE_TAG', value: '$.release.tag_name'],
                [key: 'RELEASE_ACTION', value: '$.action'],
                [key: 'RELEASE_NAME', value: '$.release.name']
            ],
            causeString: 'GitHub Release: $RELEASE_NAME ($RELEASE_TAG)',
            token: 'linkyboard-ai-release-trigger',
            printContributedVariables: true,
            printPostContent: true,
            regexpFilterText: '$RELEASE_ACTION',
            regexpFilterExpression: '^(published)$'
        )
    }

    parameters {
        string(name: 'TAG', defaultValue: '', description: '배포할 Git 태그 (예: v0.1.0)')
        string(name: 'DEPLOY_HOST', defaultValue: '', description: '배포 대상 VM IP/도메인 (기본값: Jenkins Credential에서 로드)')
        booleanParam(name: 'RUN_SMOKE', defaultValue: true, description: '배포 후 스모크 체크 실행 여부')
        booleanParam(name: 'AUTO_ROLLBACK', defaultValue: true, description: '스모크 체크 실패 시 자동 롤백 여부')
    }

    environment {
        HARBOR_REPO    = 'linkyboard/linkyboard-ai'
        LOCAL_IMAGE    = 'linkyboard-ai'

        CONTAINER_NAME = 'linkyboard-ai'

        APP_PORT       = '8000'
        HOST_PORT      = '8000'

        ENV_FILE       = '/opt/linkyboard-ai/.env.production'
        HEALTH_URL     = 'http://127.0.0.1:8000/health'

        // RESOLVED_TAG와 TARGET_HOST는 Resolve Tag 스테이지에서 동적으로 설정
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
                    // GitHub Release 트리거로 실행된 경우 RELEASE_TAG 사용, 아니면 params.TAG 사용
                    def deployTag = env.RELEASE_TAG ?: params.TAG

                    if (!deployTag?.trim()) {
                        error('TAG가 지정되지 않았습니다. GitHub Release를 생성하거나 수동으로 TAG를 입력하세요.')
                    }

                    // DEPLOY_HOST가 비어있으면 Jenkins Credential에서 로드
                    def deployHost = params.DEPLOY_HOST
                    if (!deployHost?.trim()) {
                        withCredentials([string(credentialsId: 'ai-deploy-host', variable: 'DEFAULT_HOST')]) {
                            deployHost = env.DEFAULT_HOST
                        }
                        echo "ℹ️  DEPLOY_HOST가 지정되지 않아 기본값을 사용합니다: ${deployHost}"
                    }

                    if (!deployHost?.trim()) {
                        error('DEPLOY_HOST를 지정하거나 Jenkins Credential(ai-deploy-host)을 설정하세요.')
                    }

                    // 환경변수로 설정
                    env.RESOLVED_TAG = deployTag
                    env.TARGET_HOST = deployHost

                    echo "🎯 배포 태그: ${env.RESOLVED_TAG}"
                    echo "🎯 배포 서버: ${env.TARGET_HOST}"

                    sh "git checkout ${env.RESOLVED_TAG}"
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

        stage('Capture Previous Deployment') {
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER')
                ]) {
                    script {
                        def previousImage = sh(
                            script: """
                                set -e
                                ssh -o StrictHostKeyChecking=no -i \$SSH_KEY \$SSH_USER@${TARGET_HOST} <<'ENDSSH'
                                    if docker ps --format '{{.Names}}' | grep -qx '${CONTAINER_NAME}'; then
                                        docker inspect ${CONTAINER_NAME} --format='{{.Config.Image}}' || echo 'none'
                                    else
                                        echo 'none'
                                    fi
ENDSSH
                            """,
                            returnStdout: true
                        ).trim()

                        env.PREVIOUS_IMAGE = previousImage

                        if (previousImage != 'none') {
                            echo "📦 이전 배포 이미지: ${previousImage}"
                        } else {
                            echo "ℹ️  실행 중인 컨테이너가 없습니다. 최초 배포입니다."
                        }
                    }
                }
            }
        }

        stage('Run Database Migrations') {
            steps {
                script {
                    try {
                        withCredentials([
                            usernamePassword(credentialsId: 'harbor-jenkins-bot', usernameVariable: 'H_USER', passwordVariable: 'H_PASS'),
                            string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL'),
                            sshUserPrivateKey(credentialsId: 'deploy-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER')
                        ]) {
                            sh """
                                set -e

                                ssh -o StrictHostKeyChecking=no -i \$SSH_KEY \$SSH_USER@${TARGET_HOST} <<'ENDSSH'
                                    set -e

                                    echo "🔄 데이터베이스 마이그레이션 시작..."

                                    # Harbor 로그인
                                    printf '%s\\\\n' '${H_PASS}' | docker login ${HARBOR_URL} -u '${H_USER}' --password-stdin

                                    # 마이그레이션 전용 임시 컨테이너 실행
                                    docker run --rm \
                                      --env-file ${ENV_FILE} \
                                      --network host \
                                      ${HARBOR_URL}/${HARBOR_REPO}:${RESOLVED_TAG} \
                                      alembic upgrade head

                                    # 마이그레이션 성공 확인
                                    if [ \$? -eq 0 ]; then
                                      echo "✅ 마이그레이션 완료"
                                    else
                                      echo "❌ 마이그레이션 실패"
                                      docker logout ${HARBOR_URL}
                                      exit 1
                                    fi

                                    docker logout ${HARBOR_URL}
ENDSSH
                            """
                        }
                    } catch (Exception e) {
                        env.FAILURE_STAGE = 'migration'
                        echo "❌ 마이그레이션 실패: ${e.message}"
                        throw e
                    }
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
                script {
                    def smokeCheckResult = 'unknown'
                    try {
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
                                      echo "✅ Health check OK"
                                      exit 0
                                    fi
                                    sleep 1
                                  done
                                  echo "❌ Health check failed"
                                  docker logs --tail 200 "$CONTAINER_NAME" || true
                                  exit 1
EOF
                            '''
                        }
                        smokeCheckResult = 'success'
                    } catch (Exception e) {
                        smokeCheckResult = 'failed'
                        echo "❌ 스모크 체크 실패: ${e.message}"

                        if (params.AUTO_ROLLBACK && env.PREVIOUS_IMAGE != 'none') {
                            echo "🔄 자동 롤백을 시작합니다..."

                            withCredentials([
                                usernamePassword(credentialsId: 'harbor-jenkins-bot', usernameVariable: 'H_USER', passwordVariable: 'H_PASS'),
                                string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL'),
                                sshUserPrivateKey(credentialsId: 'deploy-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER')
                            ]) {
                                sh """
                                    set -e

                                    ssh -o StrictHostKeyChecking=no -i \\$SSH_KEY \\$SSH_USER@${TARGET_HOST} <<'ENDSSH'
                                        set -e

                                        echo "🔄 롤백 시작: ${env.PREVIOUS_IMAGE}"

                                        # 실패한 컨테이너 중지 및 제거
                                        if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
                                          docker stop ${CONTAINER_NAME} || true
                                          docker rm ${CONTAINER_NAME} || true
                                        fi

                                        # 이전 이미지로 컨테이너 재시작
                                        docker run -d \
                                          --name ${CONTAINER_NAME} \
                                          --restart unless-stopped \
                                          --env-file ${ENV_FILE} \
                                          -p ${HOST_PORT}:${APP_PORT} \
                                          ${env.PREVIOUS_IMAGE}

                                        echo "⏳ 롤백된 컨테이너 헬스 체크 중..."
                                        sleep 5

                                        # 롤백된 컨테이너 헬스 체크
                                        for i in \$(seq 1 10); do
                                          if curl -fsS "${HEALTH_URL}" >/dev/null; then
                                            echo "✅ 롤백 완료 및 헬스 체크 성공"
                                            exit 0
                                          fi
                                          sleep 1
                                        done

                                        echo "⚠️  롤백은 완료되었으나 헬스 체크 실패. 컨테이너 로그 확인 필요"
                                        docker logs --tail 100 ${CONTAINER_NAME} || true
ENDSSH
                                """
                            }

                            env.ROLLBACK_PERFORMED = 'true'
                            echo "✅ 이전 버전(${env.PREVIOUS_IMAGE})으로 롤백 완료"
                        } else if (params.AUTO_ROLLBACK && env.PREVIOUS_IMAGE == 'none') {
                            echo "⚠️  이전 배포가 없어 롤백할 수 없습니다."
                            env.ROLLBACK_PERFORMED = 'none'
                        } else {
                            echo "ℹ️  자동 롤백이 비활성화되어 있습니다. 수동으로 조치가 필요합니다."
                            env.ROLLBACK_PERFORMED = 'disabled'
                        }

                        // 스모크 체크 실패는 빌드 실패로 처리
                        error("스모크 체크 실패")
                    }
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
                    def rollbackStatus = "N/A"
                    def titleEmoji = "❌"
                    def deploymentStatus = "Deployment Failed"

                    if (env.ROLLBACK_PERFORMED == 'true') {
                        rollbackStatus = "✅ 롤백 완료 (${env.PREVIOUS_IMAGE})"
                        titleEmoji = "🔄"
                        deploymentStatus = "Deployment Failed - Rolled Back"
                    } else if (env.ROLLBACK_PERFORMED == 'none') {
                        rollbackStatus = "⚠️ 롤백 불가 (최초 배포)"
                        deploymentStatus = "Deployment Failed - No Rollback"
                    } else if (env.ROLLBACK_PERFORMED == 'disabled') {
                        rollbackStatus = "ℹ️ 자동 롤백 비활성화"
                        deploymentStatus = "Deployment Failed - Manual Fix Required"
                    }

                    def payload = """
                    {
                        "username": "LinkyBoard AI CD",
                        "embeds": [{
                            "title": "${titleEmoji} AI 서버 배포 실패",
                            "color": 15158332,
                            "fields": [
                                {"name": "Version", "value": "${RESOLVED_TAG}", "inline": true},
                                {"name": "Server IP", "value": "${TARGET_HOST}", "inline": true},
                                {"name": "Status", "value": "${deploymentStatus}", "inline": false},
                                {"name": "Rollback", "value": "${rollbackStatus}", "inline": false},
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
