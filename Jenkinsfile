
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
  gitCheckout('https://github.com/tribler/gumby.git', '*/devel')
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

stage "Running tests"
node('bbq') {

  unstash 'tribler'
  unstash 'gumby'

  parallel "Linux tests": {

    try {
      sh '''
env
export TMPDIR="$PWD/tmp"
export NOSE_COVER_TESTS=1
export GUMBY_nose_tests_parallelisation=12
export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$PYTHONPATH
export PYLINTRC=$PWD/tribler/.pylintrc
ulimit -c unlimited
#gumby/run.py gumby/experiments/tribler/run_all_tests_parallel.conf
'''
    } finally {
      archive 'output/**'
      step([$class: 'JUnitResultArchiver',
            healthScaleFactor: 1000,
            testResults: '**/*nosetests.xml'])
    }
  },
  "Pylint": {

    unstash 'tribler'

    sh '''
export PATH=$PATH:$HOME/.local/bin/

mkdir -p output

cd tribler

#git branch -r
#(git diff origin/${CHANGE_TARGET}..HEAD | grep ^diff)||:

PYLINTRC=.pylintrc diff-quality --violations=pylint --options="Tribler" --compare-branch origin/${CHANGE_TARGET} --fail-under 100 --html-report ../output/quality_report.html --external-css-file ../output/style.css
'''
    dir('output') {
      publishHTML()
    }
  },
             failFast: true
}
