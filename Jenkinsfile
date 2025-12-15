pipeline {
    agent any

    parameters {
        string(
            name: 'TAG',
            defaultValue: '',
            description: '배포할 Git 태그 (예: v0.1.0)'
        )
        booleanParam(
            name: 'RUN_SMOKE',
            defaultValue: false,
            description: '배포 전 스모크 검증 단계 실행 여부(추후 활성화)'
        )
    }

    environment {
        HARBOR_REPO = 'linkyboard/linkyboard-ai'
        LOCAL_IMAGE = 'linkyboard-ai'
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
                    sh "git checkout ${params.TAG}"
                }
            }
        }

        stage('Diagnose Harbor URL Shape') {
            steps {
                withCredentials([string(credentialsId: 'harbor-ip', variable: 'HARBOR_URL')]) {
                    sh '''
                        set -e

                        if echo "$HARBOR_URL" | grep -Eq '^(http|https)://'; then
                          echo "HAS_SCHEME=yes (잘못된 값: http(s):// 제거 필요)"
                        else
                          echo "HAS_SCHEME=no"
                        fi

                        if echo "$HARBOR_URL" | grep -Eq '/.+'; then
                          echo "HAS_PATH=yes (잘못된 값: 경로 제거 필요)"
                        else
                          echo "HAS_PATH=no"
                        fi

                        if echo "$HARBOR_URL" | grep -Eq ':[0-9]+$'; then
                          echo "HAS_PORT=yes"
                        else
                          echo "HAS_PORT=no"
                        fi

                        if echo "$HARBOR_URL" | grep -Eq '^(http|https)://|/.+'; then
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
                    echo "TAG=${TAG}"

                    docker build -t ${LOCAL_IMAGE}:${TAG} -t ${LOCAL_IMAGE}:sha-${COMMIT} .
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
                        echo "Target image repository = ${IMAGE}"

                        echo "$H_PASS" | docker login "$HARBOR_URL" --username "$H_USER" --password-stdin

                        docker tag ${LOCAL_IMAGE}:${TAG} ${IMAGE}:${TAG}
                        docker tag ${LOCAL_IMAGE}:sha-${COMMIT} ${IMAGE}:sha-${COMMIT}

                        docker push ${IMAGE}:${TAG}
                        docker push ${IMAGE}:sha-${COMMIT}

                        docker logout "$HARBOR_URL"
                    '''
                }
            }
        }

        stage('Build Placeholder') {
            steps {
                echo "Jenkinsfile 실행 완료"
                echo "배포 태그: ${params.TAG}"
                echo "RUN_SMOKE: ${params.RUN_SMOKE}"
                echo "Harbor push 완료"
            }
        }
    }
}
