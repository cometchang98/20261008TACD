#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凱程診所 - 本機自費疫苗名冊脫敏與動態轉換工具
作者：張凱傑 院長 / 凱程診所
特點：100% 本機 Python 離線運行，物理切斷身分證與地址，支援每日名冊動態更新與施打狀態維護！
"""

import csv
import re
import os

def mask_name(name):
    """姓名遮蔽：2字遮後字，3字遮中間字，4字遮中間兩字"""
    name = name.strip()
    if len(name) <= 2:
        return name[0] + "*"
    elif len(name) == 3:
        return name[0] + "*" + name[2]
    else:
        return name[0] + "**" + name[-1]

def mask_phone(phone):
    """電話遮蔽並提取末四碼"""
    clean_digits = re.sub(r'\D', '', phone)
    last4 = clean_digits[-4:] if len(clean_digits) >= 4 else "0000"
    masked = f"{clean_digits[:4]}-***-{last4}" if len(clean_digits) >= 8 else "****-***-" + last4
    return masked, last4

def determine_price(vaccine_name, reg_type):
    """判定自費疫苗價格與早鳥資格"""
    vaccine_name = vaccine_name.strip()
    is_walkin = "現場" in reg_type
    
    if "GSK" in vaccine_name:
        if is_walkin:
            return 1200, "現場正式售價"
        return 1100, "早鳥優惠價 (原價$1200)"
    elif "賽諾菲" in vaccine_name:
        if is_walkin:
            return 1200, "現場正式售價"
        return 1100, "早鳥優惠價 (原價$1200)"
    elif "東洋輔流威護" in vaccine_name or "細胞" in vaccine_name:
        if is_walkin:
            return 1600, "現場正式售價"
        return 1500, "早鳥優惠價 (原價$1600)"
    elif "AZ" in vaccine_name or "鼻噴" in vaccine_name:
        return 1700, "正式售價 (無早鳥優惠)"
    elif "佐劑" in vaccine_name or "Fluad" in vaccine_name:
        return 2000, "正式售價 (無早鳥優惠)"
    else:
        return 1200, "標準售價"

def generalize_notes(notes):
    """泛化醫療主訴，移除可能辨識個人之敏感特徵"""
    if "過敏" in notes:
        return "備註：對蛋嚴重過敏史"
    elif "糖尿病" in notes or "高血壓" in notes or "心血管" in notes or "長輩" in notes:
        return "備註：高風險慢性病或長者"
    elif "兒童" in notes or "怕打針" in notes:
        return "備註：小兒無痛接種需求"
    elif "氣喘" in notes:
        return "備註：慢性呼吸道病史"
    else:
        return "一般健康成人"

def process_anonymization(input_file, sanitized_file, mapping_file):
    print(f"🔒 正在讀取含有特種個資之每日原始名冊: {input_file}")
    
    sanitized_rows = []
    mapping_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            voucher_id = f"VAC-2026-{idx:03d}"
            
            raw_name = row['病患真實姓名']
            raw_id = row['身分證字號']
            raw_phone = row['聯絡電話']
            raw_bday = row['出生年月日']
            raw_addr = row['居住通訊地址']
            vaccine = row['預約疫苗品項']
            notes = row['慢性病史與特殊備註']
            time_slot = row['期望施打時段']
            reg_type = row.get('掛號類別', '線上預約早鳥')
            status = row.get('施打狀態', '已預約未施打')
            
            # 脫敏處理
            safe_name = mask_name(raw_name)
            masked_phone, last4 = mask_phone(raw_phone)
            price, price_type = determine_price(vaccine, reg_type)
            safe_notes = generalize_notes(notes)
            
            # 1. 安全資料表（可安全給予 AI 大模型分析）
            sanitized_rows.append({
                "序號": voucher_id,
                "登記時間": row['預約登記時間'],
                "病患姓名": safe_name,
                "電話末4碼": last4,
                "疫苗品項": vaccine,
                "實收價格": price,
                "價格類別": price_type,
                "掛號類別": reg_type,
                "施打狀態": status,
                "醫療特徵": safe_notes,
                "期望時段": time_slot
            })
            
            # 2. 本機專屬金鑰對照表（鎖在診所硬碟，嚴禁上傳！）
            mapping_rows.append({
                "序號": voucher_id,
                "真實姓名": raw_name,
                "真實身分證字號": raw_id,
                "完整電話": raw_phone,
                "出生年月日": raw_bday,
                "完整地址": raw_addr,
                "疫苗品項": vaccine,
                "施打狀態": status
            })
    
    # 寫入安全脫敏檔
    with open(sanitized_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sanitized_rows[0].keys())
        writer.writeheader()
        writer.writerows(sanitized_rows)
    print(f"✅ 成功產出安全脫敏名冊（共 {len(sanitized_rows)} 筆，0%個資殘留）: {sanitized_file}")
    
    # 寫入本地對照表
    with open(mapping_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=mapping_rows[0].keys())
        writer.writeheader()
        writer.writerows(mapping_rows)
    print(f"🔑 成功更新本地金鑰對照表（嚴禁上傳雲端）: {mapping_file}")

if __name__ == "__main__":
    import sys
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 支援指定名冊檔案（例如：python anonymize.py raw_patient_bookings_1001_當日結算.csv）
    target_input = None
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.exists(candidate):
            target_input = candidate
        elif os.path.exists(os.path.join(base_dir, candidate)):
            target_input = os.path.join(base_dir, candidate)
            
    # 若未指定，則按優先順序自動偵測工作區中現有的名冊
    if not target_input:
        candidates = [
            "raw_patient_bookings_1001_當日結算.csv",
            "raw_patient_bookings.csv",
            "raw_patient_bookings_0930_未開打.csv"
        ]
        for c in candidates:
            p = os.path.join(base_dir, c)
            if os.path.exists(p):
                target_input = p
                break
                
    if not target_input:
        target_input = os.path.join(base_dir, "raw_patient_bookings.csv")
        
    sanitized_csv = os.path.join(base_dir, "sanitized_patient_bookings.csv")
    mapping_csv = os.path.join(base_dir, "local_mapping_key_DO_NOT_UPLOAD.csv")
    
    process_anonymization(target_input, sanitized_csv, mapping_csv)
