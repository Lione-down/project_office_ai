FROM paddlepaddle/paddle:3.3.1

ENV HOME=/opt/paddle-home
ENV PADDLE_OCR_BASE_DIR=/opt/paddle-home/.paddleocr
ENV PADDLE_PDX_CACHE_HOME=/opt/paddle-home/.paddlex
ENV PADDLE_PDX_MODEL_SOURCE=BOS
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir --force-reinstall paddlepaddle==3.1.1 \
    && python -m pip install --no-cache-dir paddleocr==3.7.0
RUN mkdir -p "${HOME}" \
    && python -c "from paddleocr import PaddleOCR; PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det', text_recognition_model_name='PP-OCRv5_mobile_rec', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, device='cpu')" \
    && chmod -R a=rX "${HOME}"

WORKDIR /app
COPY app /app/app

USER 10001:10001
CMD ["python", "-m", "app.services.ocr.server"]
