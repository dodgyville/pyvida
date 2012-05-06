Running
=======
By default, pyvida runs a game "as the player would see it". To assist with development, deployment and testing, pyvida also provides several commandline options. To display the available options, type: python main.py --help

Options::

  -h, --help            show this help message and exit
  -f, --fullscreen      Play game in fullscreen mode
  -p, --profile         Record player movements for testing
  -c, --characters      Print lots of info about actor and items to calculate
                        art requirements
  -s STEP, --step=STEP  Jump to step in walkthrough
  -H, --headless        Run game as headless (no video)
  -a, --artreactor      Save images from each scene
  -i, --inventory       Test each item in inventory against each item in scene
  -d ANALYSE_SCENE, --detailed <scene>=ANALYSE_SCENE
                        Print lots of info about one scene (best used with
                        test runner)
  -r, --random          Randomly deviate from walkthrough to stress test
                        robustness of scripting
  -m, --memory          Run game in low memory mode
  -e, --exceptions      Switch off exception catching.

