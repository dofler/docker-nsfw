FROM bvlc/caffe:cpu

COPY nsfw /opt/nsfw/

RUN mkdir /images                                \
    && pip install -r /opt/nsfw/requirements.txt

VOLUME /images

EXPOSE 8080

CMD python /opt/nsfw/nsfw.py
