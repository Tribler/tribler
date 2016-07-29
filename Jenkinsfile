def gitCheckout(url, branch, targetDir=''){
  if (targetDir == '') {
    targetDir = (url =~ '.*/(.+).git')[0][1]
  }
  echo "cloning ${url} to ${targetDir} and checking out branch: ${branch}"

  checkout([$class: 'GitSCM',
            userRemoteConfigs: [[url: url]],
            branches: [[name: branch]],

            doGenerateSubmoduleConfigurations: false,
            extensions: [[$class: 'CloneOption',
                          noTags: false,
                          reference: '',
                          shallow: true],

                         [$class: 'SubmoduleOption',
                          disableSubmodules: false,
                          recursiveSubmodules: true,
                          reference: '',
                          trackingSubmodules: false],

                         [$class: 'RelativeTargetDirectory',
                          relativeTargetDir: targetDir],

                         [$class: 'CleanCheckout'],

                         [$class: 'CleanBeforeCheckout']],
            submoduleCfg: [],
           ])

}

def checkoutGumby() {
  gitCheckout('https://github.com/devos50/gumby.git', '*/devos50/fix_idle_run')
}


stage "Checkout"
node {

  sh '''
env
'''
  deleteDir()

  parallel "Checkout Tribler": {


    dir('tribler') {
      sh 'echo $PWD'
      checkout scm
      // TODO: this shouldn't be necessary, but the git plugin gets really confused
      // if a submodule's remote changes.
      sh 'git submodule update --init --recursive'
    }
    stash includes: 'tribler/**', name: 'tribler'

  },
  "Checkout Gumby": {
    checkoutGumby()
    stash includes: 'gumby/**', name: 'gumby'
  }
}

stage "Running Tribler experiment"
node('bbq') {
  unstash 'tribler'
  unstash 'gumby'

  try {
    sh '''
    export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$PYTHONPATH
    ulimit -c unlimited
    gumby/run.py gumby/experiments/tribler/run_tribler.conf
    '''
  } finally {
    archive 'output/**'
  }
}
