// Jenkinsfile — Tiketin (Studi Kasus K02, Kelompok 5)
// Alur: Checkout → Test → Build Image → Push Image → Deploy → Smoke Test → Concurrency Check
// Bisa dijalankan di agent Linux (sh) maupun Windows (bat) tanpa diubah.
//
// Credentials yang harus dibuat di Jenkins (Manage Jenkins → Credentials):
//   dockerhub-credentials : Username with password (username Docker Hub + Personal Access Token)
//   tiketin-env           : Secret file (isi seperti .env.example)
//   github-credentials    : hanya jika repository private (dipakai di konfigurasi job, bukan di sini)

// Jalankan perintah dengan sh (Linux/Mac) atau bat (Windows).
def runCmd(String cmd) {
    if (isUnix()) {
        sh cmd
    } else {
        bat cmd
    }
}

// Nama image di Docker Hub, contoh: budi/tiketin
def image() {
    return "${env.DOCKERHUB_USER}/${env.IMAGE_NAME}"
}

pipeline {
    agent any

    options {
        disableConcurrentBuilds()                      // satu deploy dalam satu waktu
        buildDiscarder(logRotator(numToKeepStr: '30'))
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        DOCKERHUB_USER = 'viannnzn1221'   // <-- ganti dengan username Docker Hub kelompok
        IMAGE_NAME     = 'tiketin'
        TAG            = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT = isUnix()
                        ? sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                        : bat(returnStdout: true, script: '@git rev-parse --short HEAD').trim()
                }
                echo "Commit ${env.GIT_SHORT} | build #${env.BUILD_NUMBER} | image ${image()}"
            }
        }

        stage('Test') {
            steps {
                // Stage "test" di Dockerfile menjalankan pytest. Jika ada test gagal,
                // docker build gagal → pipeline berhenti di sini dan aplikasi lama tetap jalan.
                runCmd("docker build --target test -t ${image()}:test .")
            }
        }

        stage('Build Image') {
            steps {
                runCmd("docker build --target runtime --build-arg APP_VERSION=${env.TAG}-${env.GIT_SHORT} -t ${image()}:${env.TAG} -t ${image()}:latest .")
            }
        }

        stage('Push Image') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_PASS')]) {
                    script {
                        // tanda kutip tunggal: token tidak diinterpolasi Groovy & tidak tampil di log
                        if (isUnix()) {
                            sh 'echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin'
                        } else {
                            bat '@echo %DH_PASS%| docker login -u %DH_USER% --password-stdin'
                        }
                    }
                    runCmd("docker push ${image()}:${env.TAG}")
                    runCmd("docker push ${image()}:latest")
                }
            }
        }

        stage('Deploy') {
            steps {
                // File .env diambil dari Jenkins Credentials (Secret file), tidak ada di repository.
                withCredentials([file(credentialsId: 'tiketin-env', variable: 'ENV_FILE')]) {
                    script {
                        if (isUnix()) {
                            sh 'cp "$ENV_FILE" .env'
                        } else {
                            bat 'copy /Y "%ENV_FILE%" .env'
                        }
                    }
                }
                runCmd('docker compose pull app')
                runCmd('docker compose up -d --remove-orphans')
                runCmd('docker compose ps')
            }
        }

        stage('Smoke Test') {
            steps {
                // Memanggil GET /health aplikasi yang baru di-deploy; gagal jika bukan 200.
                runCmd('docker compose exec -T app python scripts/smoke_test.py --retries 12 --delay 5')
            }
        }

        stage('Concurrency Check') {
            steps {
                // 50 pembelian paralel ke event berkuota 20 → harus terjual tepat 20.
                runCmd('docker compose exec -T app python scripts/concurrency_check.py --requests 50 --quota 20')
            }
        }
    }

    post {
        always {
            echo """
==================== RINGKASAN PIPELINE TIKETIN ====================
Build   : #${env.BUILD_NUMBER}  (commit ${env.GIT_SHORT ?: '-'})
Image   : ${image()}:${env.TAG}  dan  ${image()}:latest
Hasil   : ${currentBuild.currentResult}
Durasi  : ${currentBuild.durationString}
URL     : ${env.BUILD_URL}
===================================================================="""
            script {
                try { runCmd('docker logout') } catch (err) { echo "docker logout dilewati: ${err}" }
            }
        }
        success {
            echo 'Pipeline SUKSES: test lolos, image ter-push ke Docker Hub, aplikasi ter-deploy, smoke test & concurrency check lolos.'
        }
        failure {
            echo 'Pipeline GAGAL: lihat stage yang merah di Stage View. Jika gagal di Test, versi lama aplikasi tetap berjalan.'
            script {
                try {
                    runCmd('docker compose ps')
                    runCmd('docker compose logs --tail=60 app')
                } catch (err) {
                    echo "Tidak bisa menampilkan status container: ${err}"
                }
            }
        }
    }
}
