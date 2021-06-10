
import sys
import numpy as np
import imageio
from matplotlib import pyplot as plt
from tqdm import tqdm


# check if a pixel is ``black''
# takes uint8
def is_black(pixel, threshold):
  # do we need to convert to int so that it works properly?
  return pixel < threshold

# convert a frame to grayscale
def grayscale(frame):
  frame = np.average(frame, axis=2)
  return frame.astype(np.uint8)

# read in a block of frames from a VideoCapture
# size = number of frames
# stride = n  means only use every nth frame
def read_block(reader, block_size, stride, crop):
  block = []
  for i in range(block_size*stride):
    try:
      frame, _ = reader._read_frame()
    except StopIteration:
      break
    if i % stride == 0:
      # convert to grayscale and crop
      frame = grayscale(frame)
      frame = frame[
          crop['top']:crop['bottom'],
          crop['left']:crop['right']
          ]
      block.append(frame)
  return np.asarray(block, dtype=np.uint8)


# find the frame on which a certain pixel gets inked
# returns the index of the frame in the buffer, or None if no ink frame found
def find_ink_frame(frame_buffer, i, j, block_size, bw_cutoff):
  # x works forwards
  # y works backwards
  # start from the middle
  x = block_size - 1
  y = 0
  while x < len(frame_buffer):
    # step back until we find a white pixel or the beginning of the buffer
    while is_black(frame_buffer[x-y,i,j], bw_cutoff) and x-y >= 0:
      y += 1
    # once we find a white pixel
    # if we've found a long enough run, return
    if y >= block_size:
      return x-y+1 # +1 because the current pixel is white
    # if not, skip forward to the next possible end of a long enough run
    else:
      x = x-y + block_size
      y = 0
  # at this point we've reached the end of the buffer without finding a long enough run
  return None


# ask for parameters
# returns list of parameters
def get_parameters():
  # defaults
  stride = 10       # stride = n  means only use every nth frame
  block_size = 60   # number of frames before a pixel is 'inked'
  bw_cutoff = 120   # threshold below which a pixel is 'black'
  only_ink_frames = False   # skip frames where no pixel changes
  outro_length = 3      # number of seconds to hold final frame at end

  print("\nplease enter parameters (or leave blank for default value)")
  try:
    stride = int(input(
        f"stride (int n -> keep every nth frame, default {stride}): "
        ))
  except ValueError:
    pass
  try:
    block_size = int(
        input(f"block_size (int frames, default {block_size}): ")
        )
  except ValueError:
    pass
  try:
    bw_cutoff = int(
        input(f"bw_cutoff (0-255 pixel intensity, default {bw_cutoff}): ")
        )
  except ValueError:
    pass
  try:
    only_ink_frames = bool(int(input(
      f"only_ink_frames (0-1 bool, default {int(only_ink_frames)}): "
      )))
  except ValueError:
    pass
  try:
    outro_length = int(
        input(f"outro_length(int seconds, default {outro_length}): ")
        )
  except ValueError:
    pass

  return stride, block_size, bw_cutoff, only_ink_frames, outro_length


# get crop
# returns dict crop = {'top' : int, 'bottom' : int, 'left' : etc...
def get_crop(final_frame):
  # show the final frame and ask for cropping
  print("please enter cropping", flush=True)
  plt.imshow(final_frame)
  plt.show(block=True)
  yn = False
  while not yn:
    crop = {
        'top' : 0,
        'bottom' : height,
        'left' : 0,
        'right' : width
        }
    try:
      crop['top'] = int(
          input(f"first row to include (int pixels, default {crop['top']}): ")
          )
    except ValueError:
      pass
    try:
      crop['bottom'] = int(
          input(f"last row to include (int pixels, default {crop['bottom']}): ")
          )
    except ValueError:
      pass
    try:
      crop['left'] = int(input(
          f"first column to include (int pixels, default {crop['left']}): "
          ))
    except ValueError:
      pass
    try:
      crop['right'] = int(input(
          f"last column to include (int pixels, default {crop['right']}): "
          ))
    except ValueError:
      pass

    print("Is this crop correct?", flush=True)
    plt.imshow(final_frame[
        crop['top']:crop['bottom'],
        crop['left']:crop['right']
        ])
    plt.show(block=True)
    yn = input("Y/y to accept, N/n to redo: ")[0] in ['Y','y']

  return crop

# main
def inker(reader, writer, verbose=False):

  if verbose: print('reading metadata ... ', flush=True)
  # read metadata
  metadata = reader.get_meta_data()
  width, height = metadata['size']
  fps = metadata['fps']
  total_frames = reader.count_frames()
  if verbose:
    print(f"width={width}", flush=True)
    print(f"height={height}", flush=True)
    print(f"fps={fps}", flush=True)
    print(f"total_frames={total_frames}", flush=True)
    print('done', flush=True)

  [
      stride,
      block_size,
      bw_cutoff,
      only_ink_frames,
      outro_length
  ] = get_parameters()

  # define effective frames, i.e. number of frames we'll actually use
  eff_frames = total_frames // stride

  # grab final frame (then re-initialize reader to get back to first frame)
  #		use '- 2' because imageio seems to dislike the final frame
  if verbose: print('processing final frame ... ', end='', flush=True)
  n = 1	# hack because imageio really struggles here
  while True:
    try:
      final_frame = reader.get_data(total_frames - n)
      break
    except IndexError:
      if verbose: print(f"could not get frame -{n}, trying -{n+stride}")
      n += stride

  crop = get_crop(final_frame)

  # crop final frame
  final_frame = final_frame[
      crop['top']:crop['bottom'],
      crop['left']:crop['right']
      ]

  reader._initialize()
  # convert -> numpy array -> grayscale -> black & white
  final_frame = np.array(final_frame, dtype=np.uint8)
  final_frame = np.average(final_frame, axis=2)
  final_frame = np.where(final_frame < bw_cutoff, 0, 255)
  # expect entries to be np.int64 at this point

  # make list of pixels which are black in the final, i.e. need to be inked
  uninked = np.where(final_frame == 0)
  uninked = list(zip(uninked[0],uninked[1]))
  if verbose: print('done', flush=True)

  # initialize matrix of ink frames
  ink_frame = np.full((
      crop['bottom']-crop['top'],
      crop['right']-crop['left']
      ), eff_frames)

  # initialize frame buffer
  if verbose: print('initializing frame buffer ... ', end='', flush=True)
  assert eff_frames > 2*block_size, "not enough frames, reduce block size or stride"
  frame_buffer = read_block(reader, block_size, stride, crop)
  frame_buffer = np.concatenate((
                  frame_buffer,
                  read_block(reader, block_size, stride, crop)
                  ))
  if verbose: print('done', flush=True)


  # main processing loop

  for block_number in tqdm(range(eff_frames//block_size - 1)):
    # search for new ink frames
    if verbose: print('searching for ink frames ... ', end='', flush=True)
    new_inked_pixels = []	# pixels to remove from uninked list
    new_inked_frames = []	# list of frames in which a new pixel is inked
    for [i,j] in uninked:
      f = find_ink_frame(frame_buffer, i, j, block_size, bw_cutoff)
      if f != None:
        ink_frame[i][j] = block_number*block_size + f
        new_inked_pixels.append([i,j])
        new_inked_frames.append(f)
    # remove pixels we just inked from uninked list
    if verbose: count_new_inked = 0
    for [i,j] in new_inked_pixels:
      if verbose: count_new_inked += 1
      uninked.remove((i,j))
    if verbose:
      print(
          f'{count_new_inked} pixels inked in block {block_number}\ndone',
          flush=True
          )

    # rewrite frames in front block
    if verbose: print('computing frames ... ', end='', flush=True)
    for f in range(block_size):
      current_frame = block_number*block_size + f
      frame_buffer[f] = np.where(ink_frame <= current_frame, 0, 255)
    if verbose: print('done', flush=True)
    # write front block to output
    if verbose: print('writing frames to file ... ', end='', flush=True)
    for f in range(block_size):
      if only_ink_frames and f not in new_inked_frames:
        pass
      else:
        writer.append_data(frame_buffer[f])
    if verbose: print('done', flush=True)
    # delete front block and read in new block
    if verbose: print('reading new block ... ', end='', flush=True)
    frame_buffer = frame_buffer[block_size:]
    try:
      frame_buffer = np.concatenate((
                          frame_buffer,
                          read_block(reader, block_size, stride, crop)
                          ))
    except Exception as error:
      print(f"block number: {block_number}/{eff_frames//block_size-2}")
      print(f"total frames: {total_frames}")
      print(f"effective frames: {eff_frames}")
      print(f"block size: {block_size}")
      raise error
    if verbose: print('done', flush=True)

  # Final processing when we've run out of blocks
  # 	at this point frame_buffer should contain 1 full block
  #		plus the rest of the frames
  if verbose: print('final processing loop ... ', end='', flush=True)

  block_number = eff_frames//block_size - 1

  # search for new ink frames
  new_inked_pixels = []
  new_inked_frames = []
  for [i,j] in uninked:
    # step back until we reach a white frame or run out of buffer
    x = len(frame_buffer) - 1
    y = 0
    if not is_black(frame_buffer[x-y][i][j], bw_cutoff):
      y = 1
      # shouldn't happen, uninked list only has pixels black in final frame
      assert False, "uninked pixel not black in final frame"
    while x-y >= 0 and is_black(frame_buffer[x-y][i][j], bw_cutoff):
      y += 1
    f = x-y+1
    ink_frame[i][j] = block_number*block_size + f
    new_inked_pixels.append([i,j])
    new_inked_frames.append(f)
  for [i,j] in new_inked_pixels:
    uninked.remove((i,j))

  # set the rest of pixel values
  for f in range(len(frame_buffer)):
    current_frame = block_number*block_size + f
    frame_buffer[f] = np.where(ink_frame > current_frame, 255, 0)

  # write everything to output
  for f in range(len(frame_buffer)):
    if only_ink_frames and f not in new_inked_frames:
      pass
    else:
      writer.append_data(frame_buffer[f])
  # write outro
  for _ in range(int(outro_length * fps)):
    writer.append_data(frame_buffer[-1])

  if verbose: print('done', flush=True)


