import joblib, json, re
import numpy as np
from typing import Union, Dict, Any
from pythainlp.tokenize import word_tokenize
from pythainlp.corpus.common import thai_stopwords
from pythainlp import word_vector
from json.decoder import JSONDecodeError

class prediction:
    def __init__(
        self,
        input_json: Union[str, dict],
        main_model_path: str = "./model/voting_soft_best_v2.pkl",
        sub_personal_path: str = "./model/sub_model_personal.pkl",
        sub_invest_path: str = "./model/sub_model_invest.pkl",
        sub_assets_path: str = "./model/sub_model_assets.pkl",
        sub_easy_path: str = "./model/sub_model_easy_receipt.pkl",
        sub_donation_path: str = "./model/sub_model_donation.pkl",
    ):
        self.input_json_raw = input_json
        
        # โหลดโมเดลหลัก
        self.main_model = joblib.load(main_model_path)
        
        # โหลด sub-models (รูปแบบไฟล์ต้องเป็น tuple: (model, vectorizer))
        self.sub_model_personal, self.sub_vec_personal = joblib.load(sub_personal_path)
        self.sub_model_invest,   self.sub_vec_invest   = joblib.load(sub_invest_path)
        self.sub_model_assets,   self.sub_vec_assets   = joblib.load(sub_assets_path)
        self.sub_model_easy,     self.sub_vec_easy     = joblib.load(sub_easy_path)
        self.sub_model_donation, self.sub_vec_donation = joblib.load(sub_donation_path)
        
        # โหลด Thai2Vec
        self.thai2vec_model = word_vector.WordVector(model_name="thai2fit_wv").get_model()
        self.stopwords = set(thai_stopwords())
        
    @staticmethod
    def safe_json_loads(text: str) -> dict:
        try:
            return json.loads(text)
        except JSONDecodeError:
            # ตัดจากจุดเริ่มต้น { ไปจนถึง }
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise
        
    # ฟังก์ชันแปลงข้อความเป็นเวกเตอร์
    def sentence_vector(self, sentence):
        words = word_tokenize(sentence, engine="newmm")
        vectors = [self.thai2vec_model[word] for word in words if word in self.thai2vec_model]
        if vectors:
            return np.mean(vectors, axis=0)
        else:
            return np.zeros(self.thai2vec_model.vector_size)
        
    def preprocess_text(self, text):
        text = re.sub(r'[^\u0E00-\u0E7Fa-zA-Z0-9\s]', '', text)
        tokens = word_tokenize(text.lower())
        return " ".join([t for t in tokens if t not in self.stopwords])
    
    def _predict_category(self, cleaned_name: str) -> str:
        vec = self.sentence_vector(cleaned_name).reshape(1, -1)
        return self.main_model.predict(vec)[0]
    
    def _predict_sub(self, cat: str, cleaned_name: str) -> str:
        if cat == "สิทธิลดหย่อนส่วนตัวและครอบครัว":
            X = self.sub_vec_personal.transform([cleaned_name])
            return self.sub_model_personal.predict(X)[0]
        elif cat == "การออมการลงทุนและประกัน":
            X = self.sub_vec_invest.transform([cleaned_name])
            return self.sub_model_invest.predict(X)[0]
        elif cat == "สินทรัพย์และมาตรการนโยบายภาครัฐ":
            X = self.sub_vec_assets.transform([cleaned_name])
            return self.sub_model_assets.predict(X)[0]
        elif cat == "Easy E-Receipt":
            X = self.sub_vec_easy.transform([cleaned_name])
            return self.sub_model_easy.predict(X)[0]
        elif cat == "เงินบริจาค":
            X = self.sub_vec_donation.transform([cleaned_name])
            return self.sub_model_donation.predict(X)[0]
        else:
            return "ไม่ทราบหมวดหมู่"
    
    def run(self) -> Dict[str, Any]:
        data = self.input_json_raw
        if isinstance(data, str):
            data = self.safe_json_loads(data)

        # ใช้ title ของ document-level
        title = data.get("title", "")
        print(title)

        cleaned = self.preprocess_text(title)
        print(f"Processing item: {cleaned}")

        cat = self._predict_category(cleaned)
        sub = self._predict_sub(cat, cleaned)

        # เก็บ category/sub_category ที่ระดับ document
        data["category"] = cat
        data["sub_category"] = sub

        return data
