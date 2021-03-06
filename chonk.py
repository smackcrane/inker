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
#	process video
#

inker(reader, writer, verbose=verbose)

#
# clean up
#

if verbose: print('cleaning up ... ', end='', flush=True)
reader.close()
writer.close()
if verbose: print('done', flush=True)
