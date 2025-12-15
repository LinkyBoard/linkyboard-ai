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
        // Harbor 프로젝트/레포 경로만 맞게 수정하세요. (예: linkyboard/ai)
        // 최종 이미지: <harbor-url>/<HARBOR_REPO>:<TAG>
        HARBOR_REPO = 'linkyboard/linkyboard-ai'
    }

    stage('Debug Harbor URL') {
        steps {
            withCredentials([string(credentialsId: 'harbor-url', variable: 'HARBOR_URL')]) {
                sh 'echo "HARBOR_URL=$HARBOR_URL"'
            }
        }
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

                    # 로컬 태그로 먼저 빌드
                    docker build -t linkyboard-ai:${TAG} -t linkyboard-ai:sha-${COMMIT} .
                '''
            }
        }

        stage('Push to Harbor') {
            steps {
                withCredentials([
                    usernamePassword(credentialsId: 'harbor-cred', usernameVariable: 'H_USER', passwordVariable: 'H_PASS'),
                    string(credentialsId: 'harbor-url', variable: 'HARBOR_URL')
                ]) {
                    sh '''
                        set -e
                        COMMIT=$(git rev-parse --short HEAD)

                        IMAGE="${HARBOR_URL}/${HARBOR_REPO}"

                        echo "$H_PASS" | docker login "$HARBOR_URL" -u "$H_USER" --password-stdin

                        # Harbor 태그로 다시 태깅
                        docker tag linkyboard-ai:${TAG} ${IMAGE}:${TAG}
                        docker tag linkyboard-ai:sha-${COMMIT} ${IMAGE}:sha-${COMMIT}

                        # Push
                        docker push ${IMAGE}:${TAG}
                        docker push ${IMAGE}:sha-${COMMIT}

                        docker logout "$HARBOR_URL"
                    '''
                }
            }
        }

        stage('Build Placeholder') {
            steps {
                echo "Jenkinsfile 정상 실행 확인"
                echo "배포 태그: ${params.TAG}"
                echo "RUN_SMOKE: ${params.RUN_SMOKE}"
                echo "Harbor push 완료(성공 시)"
            }
        }
    }
}
