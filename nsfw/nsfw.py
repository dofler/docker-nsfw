import requests, numpy, os, sys, glob, time, caffe, imagehash
from PIL import Image
from requests_file import FileAdapter
from flask import Flask, request, jsonify
from StringIO import StringIO

if __name__ == '__main__' and os.environ.get('DEBUG', '0') is '1':
    import ptvsd
    ptvsd.enable_attach('docker-nsfw', address = ('0.0.0.0', 4002))

s = requests.Session()
s.mount('file://', FileAdapter())
app = Flask(__name__)
app.config.from_object('config')


# Caffe Stuff
network = caffe.Net(
    app.config['CAFFE_MODEL_DEFINITIONS'],
    app.config['CAFFE_PRETRAINING'],
    caffe.TEST
)
transformer = caffe.io.Transformer({
    'data': network.blobs['data'].data.shape
})
transformer.set_transpose('data', (2, 0, 1))
transformer.set_mean('data', numpy.array([104, 117, 123]))
transformer.set_raw_scale('data', 255)
transformer.set_channel_swap('data', (2, 1, 0))


def resize_image(image):
    '''
    Resizes the image to a size that is relevent to the yahoo data
    '''

    # If the image isn't in RGB mode, we will need to convert it.
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Now lets resize the image and save it into a StringIO buffer
    # as a JPEG image.
    rimg = image.resize((256, 256), resample=Image.BILINEAR)
    resp = StringIO()
    rimg.save(resp, format='JPEG')

    # Return the byte array of the image.
    resp.seek(0)
    return bytearray(resp.read())


def compute(image_data):
    '''
    Computes the image nsfw score
    '''

    layers = app.config['CAFFE_OUTPUT_LAYERS']

    # Lets resize the image and load the image into Caffe
    rimg = resize_image(image_data)
    img = caffe.io.load_image(StringIO(rimg))

    # Compute the perceptional hash
    phash = imagehash.average_hash(image_data)

    # Now we will want to crop the image down.
    H, W, _ = img.shape
    _, _, h, w = network.blobs['data'].data.shape
    h_off = max((H - h) /2, 0)
    w_off = max((W - w) /2, 0)
    crop = img[h_off:h_off + h, w_off:w_off + w, :]

    # Now lets transform the image
    timg = transformer.preprocess('data', crop)
    timg.shape = (1,) + timg.shape

    # And to get all of the outputs
    outputs = network.forward_all(blobs=layers, **{network.inputs[0]: timg})

    # now to finally return the score
    return {
        'score': outputs[layers[0]][0].astype(float)[1] * 100,
        'phash': str(phash)
    }


@app.route('/score', methods=['POST'])
def get_score():
    image = None

    if 'image' in request.files:
        image = Image.open(request.files['image'])
    elif 'path' in request.form:
        resp = s.get(request.form.get('path'), stream=True)
        if resp.status_code == 200:
            resp.raw.decode_content = True
            image = Image.open(resp.raw)

    if image:
        try:
            scores = compute(image)
        except:
            return jsonify({'error': True})
        else:
            scores['error'] = False
            return jsonify(scores)
    else:
        return jsonify({'error': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
