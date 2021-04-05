
import sys
import numpy as np
import imageio
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
def read_block(reader, block_size):
	block = []
	for _ in range(block_size):
		try:
			frame, _ = reader._read_frame()
		except StopIteration:
			break
		frame = grayscale(frame)
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

# main
def inker(reader, writer,
		block_size, bw_cutoff, only_ink_frames, outro_length):

	# read metadata
	metadata = reader.get_meta_data()
	width, height = metadata['size']
	fps = metadata['fps']
	total_frames = reader.count_frames()

	# grab final frame (then re-initialize reader to get back to first frame)
	#		use '- 2' because imageio seems to dislike the final frame
	final_frame = reader.get_data(total_frames - 3)
	reader._initialize()
	# convert -> numpy array -> grayscale -> black & white
	final_frame = np.array(final_frame, dtype=np.uint8)
	final_frame = np.average(final_frame, axis=2)
	final_frame = np.where(final_frame < bw_cutoff, 0, 255)
	# expect entries to be np.int64 at this point

	# make list of pixels which are black in the final, i.e. need to be inked
	uninked = np.where(final_frame == 0)
	uninked = list(zip(uninked[0],uninked[1]))

	# initialize matrix of ink frames
	ink_frame = np.full((height, width), total_frames)

	# initialize frame buffer
	assert total_frames > 2*block_size, "video too short, reduce block size"
	frame_buffer = read_block(reader, block_size)
	frame_buffer = np.concatenate((frame_buffer,
																	read_block(reader, block_size)))


	# main processing loop
	
	for block_number in tqdm(range(total_frames//block_size - 1)):
		# search for new ink frames
		new_inked_pixels = []	# pixels to remove from uninked list
		new_inked_frames = []	# list of frames in which a new pixel is inked
		for [i,j] in uninked:
			f = find_ink_frame(frame_buffer, i, j, block_size, bw_cutoff)
			if f != None:
				ink_frame[i][j] = block_number*block_size + f
				new_inked_pixels.append([i,j])
				new_inked_frames.append(f)
		# remove pixels we just inked from uninked list
		for [i,j] in new_inked_pixels:
			uninked.remove((i,j))

		# rewrite frames in front block
		for f in range(block_size):
			current_frame = block_number*block_size + f
			frame_buffer[f] = np.where(ink_frame <= current_frame, 0, 255)
		# write front block to output
		for f in range(block_size):
			if only_ink_frames and f not in new_inked_frames:
				pass
			else:
				writer.append_data(frame_buffer[f])
		# delete front block and read in new block
		frame_buffer = frame_buffer[block_size:]
		try:
			frame_buffer = np.concatenate((frame_buffer,
																			read_block(reader, block_size)))
		except Exception as error:
			print(f"block number: {block_number}/{total_frames//block_size-2}")
			print(f"total frames: {total_frames}")
			print(f"block size: {block_size}")
			raise error

	# Final processing when we've run out of blocks
	# 	at this point frame_buffer should contain 1 full block
	#		plus the rest of the frames

	block_number = total_frames//block_size - 1

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



