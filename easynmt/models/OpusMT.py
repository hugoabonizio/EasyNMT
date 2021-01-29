import time
from transformers import MarianMTModel, MarianTokenizer
import os
import json
import torch
from typing import List
import logging

logger = logging.getLogger(__name__)


class OpusMT:
    def __init__(self, model_path: str, max_loaded_models: int = 10, fp16=False):
        self.model_path = model_path
        self.models = {}
        self.fp16 = fp16

        with open(os.path.join(model_path, 'easynmt.json'), encoding='utf8') as fIn:
            self.config = json.load(fIn)

        self.max_loaded_models = max_loaded_models

    def load_model(self, model_name, device):
        if model_name in self.models:
            self.models[model_name]['last_loaded'] = time.time()
            return self.models[model_name]['tokenizer'], self.models[model_name]['model']
        else:
            logger.info("Load model: "+model_name)
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
            model.eval()
            model.to(device)

            if self.fp16 and next(model.parameters()).is_cuda:
                model.half()

            if len(self.models) >= self.max_loaded_models:
                oldest_time = time.time()
                oldest_model = None
                for model_name in self.models:
                    if self.models[model_name]['last_loaded'] <= oldest_time:
                        oldest_model = model_name
                        oldest_time = self.models[model_name]['last_loaded']
                del self.models[oldest_model]

            self.models[model_name] = {'tokenizer': tokenizer, 'model': model, 'last_loaded': time.time()}
            return tokenizer, model

    def translate_sentences(self, sentences: List[str], source_lang: str, target_lang: str, device: str, beam_size: int = 5, max_length: int = None, do_sample=False, top_k=50, top_p=1.0):
        model_name = 'Helsinki-NLP/opus-mt-{}-{}'.format(source_lang, target_lang)
        tokenizer, model = self.load_model(model_name, device)

        inputs = tokenizer.prepare_seq2seq_batch(sentences, max_length=max_length, return_tensors="pt")

        for key in inputs:
            inputs[key] = inputs[key].to(device)

        with torch.no_grad():
            translated = model.generate(**inputs, num_beams=beam_size, do_sample=do_sample, top_k=top_k, top_p=top_p)
            output = [tokenizer.decode(t, skip_special_tokens=True) for t in translated]

        return output

