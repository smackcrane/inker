#!/bin/python3

import sys
import os.path
from inker import *


# define parameters for transformation
block_size = 60		# number of frames before a pixel is 'inked'
bw_cutoff = 120		# threshold below which a pixel is 'black'
only_ink_frames = True		# skip frames where no pixel changes
outro_length = 3			# number of seconds to hold final frame at end


#
#	read input file and optional output file from command line
#

if '--verbose' in sys.argv:
	verbose = True
	sys.argv.remove('--verbose')
elif '-v' in sys.argv:
	verbose = True
	sys.argv.remove('-v')
else:
	verbose = False

assert len(sys.argv) > 1, "need a video file to chonk"

in_file = sys.argv[1]
if len(sys.argv) > 2:
	out_file = sys.argv[2]
else:
	out_file = f"out.{in_file}"
assert not os.path.isfile(out_file), f"out file {out_file} already exists"


#
#	open imageio video reader and writer
#

if verbose: print('opening imageio reader ... ', end='', flush=True)
try:
	reader = imageio.get_reader(in_file)
except:
	raise
if verbose: print('done', flush=True)

metadata = reader.get_meta_data()
fps = metadata['fps']

if verbose: print('opening imageio writer ... ', end='', flush=True)
try:
	writer = imageio.get_writer(out_file, fps=fps)
except:
	raise
if verbose: print('done', flush=True)

#
# ask for parameters
#

# defaults
block_size = 60		# number of frames before a pixel is 'inked'
bw_cutoff = 120		# threshold below which a pixel is 'black'
only_ink_frames = False		# skip frames where no pixel changes
outro_length = 3			# number of seconds to hold final frame at end

print("please enter parameters (or leave blank for default value)")
try:
  block_size = int(input(f"block_size (int frames, default {block_size}): "))
except ValueError:
  pass
try:
  bw_cutoff = int(
      input(f"bw_cutoff (0-255 pixel intensity, default {bw_cutoff}): ")
      )
except ValueError:
  pass
try:
  only_ink_frames = bool(
      int(input(f"only_ink_frames (0-1 bool, default {int(only_ink_frames)}): "))
      )
except ValueError:
  pass
try:
  outro_length = int(
      input(f"outro_length(int seconds, default {outro_length}): ")
      )
except ValueError:
  pass


#
#	process video
#

inker(reader,
			writer,
			block_size,
			bw_cutoff,
			only_ink_frames,
			outro_length,
			verbose=verbose)

#
# clean up
#

if verbose: print('cleaning up ... ', end='', flush=True)
reader.close()
writer.close()
if verbose: print('done', flush=True)
