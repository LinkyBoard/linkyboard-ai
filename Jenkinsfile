pipeline {
    agent any

    parameters {
        string(
            name: 'TAG',
            defaultValue: '',
            description: '배포할 Git 태그 (예: v1.0.0)'
        )
        booleanParam(
            name: 'RUN_SMOKE',
            defaultValue: false,
            description: '배포 전 스모크 검증 단계 실행 여부'
        )
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
                        error('TAG 파라미터는 필수입니다. 예: v1.0.0')
                    }
                    sh "git checkout ${params.TAG}"
                }
            }
        }

        stage('Build Placeholder') {
            steps {
                echo "Jenkinsfile 정상 실행 확인"
                echo "배포 태그: ${params.TAG}"
                echo "RUN_SMOKE: ${params.RUN_SMOKE}"
            }
        }
    }
}
