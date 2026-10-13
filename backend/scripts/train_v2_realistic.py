"""Train v2: expand dataset with real-life + hypothetical cases, retrain TF-IDF+LR."""
import sys
sys.path.insert(0, r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')

import shutil
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, average_precision_score, f1_score

BASE = Path(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data')
BACKEND = Path(r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')

# ---------- 1. Real-life + hypothetical new cases (hand-written, diverse wording) ----------
# (text, url, category)
NEW_SCAM = [
 # OTP / bank KYC real-life
 ("SBI alert: your account will be blocked today. Complete KYC now, share OTP sent to your mobile, otherwise transactions stopped.", "", "PHISHING"),
 ("Dear customer your HDFC netbanking is suspended due to KYC pending. Verify immediately on the link and enter login password.", "http://hdfc-kyc-verify.example/login", "PHISHING"),
 ("I am calling from bank head office. Your card is blocked. Tell me the OTP you just received so I can unblock it.", "", "PHISHING"),
 ("Your electricity connection will be cut tonight at 9pm due to unpaid bill Rs 2840. Pay now on this link to avoid disconnection.", "http://eb-bill-pay-fast.example/pay", "PAYMENT_SCAM"),
 ("Electricity dept notice: last warning, your meter will be disconnected. Contact officer on WhatsApp and pay pending dues via UPI.", "", "PAYMENT_SCAM"),
 ("KBC lottery: you won Rs 25 lakh. To claim, pay Rs 12500 registration tax on WhatsApp number and share Aadhaar copy.", "", "PAYMENT_SCAM"),
 ("Congratulations you won a Maruti Swift in Dhanlaxmi lucky draw. Deposit Rs 9800Refundable processing charge to release prize.", "", "PAYMENT_SCAM"),
 ("Flipkart sale winner: iPhone 15 for Rs 499 only for you. Click and enter card CVV to grab before stock ends in 10 minutes.", "http://flipkart-offer-deals.example/win", "PHISHING"),
 ("Your parcel from FedEx is held at customs Delhi. Pay Rs 1450 clearance fee with card details on the link within 6 hours.", "http://parcel-release-customs.example/track", "PAYMENT_SCAM"),
 ("Speed post: address mismatch, your package cannot be delivered. Update address and pay Rs 49 redelivery fee here.", "http://indiapost-reschedule.example/redeliver", "PHISHING"),
 ("Hi, I accidentally sent Rs 8500 to your UPI. Please return urgently, my mother is in hospital, account will freeze otherwise.", "", "PAYMENT_SCAM"),
 ("Pay Rs 1 to this QR to receive your Rs 45000 refund. Enter UPI PIN to confirm receipt of money.", "", "PAYMENT_SCAM"),
 ("Cashback offer: scan this QR code and enter PIN to get Rs 5000 cashback instantly. Valid for next 15 minutes only.", "", "PAYMENT_SCAM"),
 ("OLX buyer: I am army officer posted in Leh. I will pay advance Rs 20000 for your bike. Scan QR and enter PIN to receive token.", "", "PAYMENT_SCAM"),
 ("Rental flat confirmed in Bangalore, owner in Dubai. Send Rs 8000 token advance on GPay to reserve, many buyers waiting, hurry.", "", "PAYMENT_SCAM"),
 ("Work from home: like YouTube videos, earn Rs 5000 daily. Join Telegram @earnfast, pay Rs 199 activation to start tasks.", "", "FAKE_JOB"),
 ("Part time captcha filling job, Rs 12000 weekly, no skill needed. Deposit Rs 550 registration to get login id today.", "", "FAKE_JOB"),
 ("Data entry job, salary Rs 35000, direct joining without interview. Send bank details plus Rs 1100 ID card charge.", "", "FAKE_JOB"),
 ("You are shortlisted for Infosys trainee role with 9 LPA. No interview. Pay Rs 3200 document verification to HR personal UPI.", "", "FAKE_JOB"),
 ("Amazon captcha work: 200 forms daily, Rs 25000 monthly. First pay training deposit Rs 1500 refundable after first salary.", "", "FAKE_JOB"),
 ("Telegram prepaid task scam: invest Rs 1000 get Rs 1300 in 1 hour. Recharge more to unlock bigger profit slab, withdraw anytime.", "", "PAYMENT_SCAM"),
 ("Crypto doubling: send 0.01 BTC, get 0.02 BTC back in 20 minutes. Celebrity giveaway, only 100 slots left, act now.", "", "PAYMENT_SCAM"),
 ("Forex trading guru: guaranteed 5x returns in 7 days. Deposit Rs 10000 to our wallet, profits credited daily on WhatsApp.", "", "PAYMENT_SCAM"),
 ("Instant loan approved Rs 50000 at 2% interest, no CIBIL needed. Pay Rs 2500 insurance fee first to release amount in 10 min.", "", "PAYMENT_SCAM"),
 ("PM Mudra loan of Rs 2 lakh sanctioned in your name. Transfer Rs 4500 file charge to agent to credit money today.", "", "PAYMENT_SCAM"),
 ("Your PAN is linked to money laundering case. Mumbai cyber police warrant issued. Pay Rs 75000 to verify and avoid arrest.", "", "PHISHING"),
 ("CBI officer on video call: you are under digital arrest for 48 hours. Do not cut call. Transfer funds to RBI safe account.", "", "PHISHING"),
 ("Traffic challan Rs 2000 pending, pay now else licence suspended. Click link and enter netbanking credentials to clear.", "http://echallan-clear-fast.example/pay", "PHISHING"),
 ("Income tax refund Rs 18450 approved. Claim by entering bank login and card expiry on the refund portal link.", "http://it-refund-claim.example/verify", "PHISHING"),
 ("Your Instagram account has copyright violation, will be deleted in 24h. Appeal by logging in with password on this page.", "http://insta-appeal-form.example/login", "PHISHING"),
 ("WhatsApp job: hotel rating task, Rs 200 per review. Deposit Rs 2000 to activate wallet, complete 30 orders daily.", "", "FAKE_JOB"),
 ("College scholarship Rs 50000 approved by UGC. Share bank netbanking password and Rs 999 verification fee to release funds.", "", "FAKE_SCHOLARSHIP"),
 ("NSP scholarship rejected due to bank error. Re-apply on this lookalike portal with full card number and OTP.", "http://nsp-scholarship-apply.example/form", "FAKE_SCHOLARSHIP"),
 ("AICTE internship with Google, stipend Rs 40000, certificate assured. Pay Rs 1800 onboarding kit fee on personal number.", "", "FAKE_INTERNSHIP"),
 ("Winter internship at Microsoft, work from phone only, no interview. Transfer Rs 1299 seat confirmation to UPI id fast.", "", "FAKE_INTERNSHIP"),
 ("Campus ambassador for Boat headphones: earn Rs 15000 monthly. Buy Rs 2499 welcome kit to unlock referral income.", "", "FAKE_AMBASSADOR"),
 ("Brand promoter needed for college fest, Rs 8000 per day. Pay Rs 700 refundable security to confirm your slot now.", "", "FAKE_AMBASSADOR"),
 ("Full stack course with 100% placement in TCS, fee Rs 60000 but pay Rs 5000 token today, only 2 seats left in batch.", "", "FAKE_TRAINING"),
 ("Data science with job guarantee or full refund. Enrol now with Rs 9999 advance to personal account, offer ends midnight.", "", "FAKE_TRAINING"),
 ("Placement drive with 12 MNCs tomorrow, assured offer for all branches. Pay Rs 2200 registration on Google form link.", "", "FAKE_PLACEMENT"),
 ("Your name is shortlisted in TCS NQT final list. Pay Rs 3100 training bond to coordinator to receive offer letter.", "", "FAKE_PLACEMENT"),
 ("Offer letter from Wipro, CTC 7.5 LPA, joining Monday. Pay Rs 4800 medical and uniform fee to HR officer account.", "", "FAKE_OFFER_LETTER"),
 ("Appointment letter attached from Accenture. Sign and return with Rs 2500 background verification charge via Paytm.", "", "FAKE_OFFER_LETTER"),
 ("Customer care: your Paytm KYC expired. Share OTP to keep wallet active, else balance frozen after today.", "", "PHISHING"),
 ("Jio tower installation: earn Rs 30000 rent monthly. Pay Rs 5900 legal fee to install tower on your rooftop.", "", "PAYMENT_SCAM"),
 ("Petrol pump dealership allotted in your name by HPCL. Pay Rs 50000 licence advance to confirm allotment today.", "", "PAYMENT_SCAM"),
 ("Relative in trouble message: beta I changed my number, urgently send Rs 15000 on this UPI, will return tomorrow morning.", "", "PAYMENT_SCAM"),
 ("Romance trick: hi dear I am US army doctor, I sent you gift parcel worth $5000, pay Rs 12000 customs to receive it.", "", "PAYMENT_SCAM"),
 ("Sextortion style: I hacked your phone camera, I have your private videos. Send Rs 20000 in bitcoin or I leak them.", "", "PHISHING"),
 ("Tech support: your computer has virus, call Microsoft helpline number now and share screen + card for cleanup Rs 1999.", "", "PHISHING"),
 ("Fake invoice: your subscription renewed Rs 9999. Call this number to cancel refund, share UPI PIN for reversal.", "", "PAYMENT_SCAM"),
 ("Bus ticket KYC: your RedBus wallet blocked. Verify with Aadhaar number and OTP on the link to continue booking.", "http://redbus-wallet-kyc.example/verify", "PHISHING"),
 ("Facebook marketplace: buyer sent extra Rs 10000 by mistake for Rs 2000 item. Return difference now via UPI urgently.", "", "PAYMENT_SCAM"),
 ("Gift task: complete 5 prepaid merchant payments of Rs 5000 each, get 20% commission. Recharge wallet first on Telegram.", "", "PAYMENT_SCAM"),
 ("Share market tips group: 95% accuracy, Rs 50000 profit weekly. Pay Rs 5000 membership to join VIP signals channel.", "", "PAYMENT_SCAM"),
 ("Aadhaar card deactivated. Update mobile linking immediately via this OTP link else bank accounts frozen.", "http://uidai-link-update.example/otp", "PHISHING"),
 ("PM Kisan Rs 6000 installment blocked. Complete e-KYC by entering bank details and OTP on this page today.", "http://pmkisan-ekyc-fast.example/login", "PHISHING"),
 ("CoWIN vaccine certificate correction: pay Rs 100 fee and enter card OTP to download updated certificate.", "", "PAYMENT_SCAM"),
 ("Dating app match asked to shift to WhatsApp in 2 messages, then asks for gift cards to meet in person tomorrow.", "", "PAYMENT_SCAM"),
 ("Freelance client overpays Rs 40000 cheque for Rs 8000 logo work, asks to refund Rs 32000 via UPI before cheque clears.", "", "PAYMENT_SCAM"),
 ("Fake professor: submit thesis printing fee Rs 3500 to personal UPI before viva, else hall ticket withheld.", "", "FAKE_PLACEMENT"),
 ("Hostel room upgrade confirmed if you pay Rs 5000 maintenance advance to senior's number before warden meeting.", "", "PAYMENT_SCAM"),
 ("Library: your account has Rs 50 fine only. Pay at counter with ID during working hours.", "", "LEGIT_MARKER"),  # intentional mislabel guard (will fix below)
]

NEW_LEGIT = [
 ("Your HDFC account ending 4521 is debited Rs 1299 for electricity bill on official app. Never share OTP, bank never asks.", "", "LEGITIMATE"),
 ("SBI reminder: KYC update only at branch or official YONO app. Do not click links in SMS asking for password.", "", "LEGITIMATE"),
 ("Electricity bill of Rs 1840 for October is due on 15th. Pay on official discom portal or app. No disconnection before due date.", "", "LEGITIMATE"),
 ("Your Amazon order arriving Thursday. Track in the Amazon app under Your Orders. No extra fee needed for delivery.", "", "LEGITIMATE"),
 ("Interview invite: Software Intern round on Friday 11am over Google Meet from careers@company.com. Bring resume and ID.", "", "LEGITIMATE"),
 ("Training and Placement Cell: Infosys drive on 20 Nov in seminar hall. Register on college ERP, no fee charged.", "", "LEGITIMATE"),
 ("Offer letter for Analyst role, joining 5 Jan. Accept on official candidate portal. Company does not ask for payment.", "", "LEGITIMATE"),
 ("NSP scholarship merit list published on scholarships.gov.in. Check with application ID. No fee to check status.", "", "LEGITIMATE"),
 ("AICTE internship portal lists approved internships. Apply with resume, selection via interview, no registration charge.", "", "LEGITIMATE"),
 ("Your application for Product Intern is under review. HR will contact from official domain within two weeks.", "", "LEGITIMATE"),
 ("Semester exam fee Rs 2500 due 30 Nov. Pay on college ERP only. Keep receipt. Contact accounts office for help.", "", "LEGITIMATE"),
 ("Hostel fee receipt available in student portal under Payments. Report errors to warden office in writing.", "", "LEGITIMATE"),
 ("Library fine Rs 20. Pay at circulation desk with college ID between 9am and 5pm on working days.", "", "LEGITIMATE"),
 ("Hackathon on 14 Dec is free for students. Form teams of 3 on the official college website by 10 Dec.", "", "LEGITIMATE"),
 ("Machine learning seminar moved to room 301 at 2pm. Notes shared in classroom drive folder.", "", "LEGITIMATE"),
 ("Project meeting at 4pm in lab 2. Bring laptop and previous readings. Inform guide if delayed.", "", "LEGITIMATE"),
 ("Bank will never ask for OTP, CVV or PIN on call or SMS. Report fraud on 1930 or cybercrime.gov.in immediately.", "", "LEGITIMATE"),
 ("Cyber cell advisory: verify offer letters on company website. Genuine recruiters never demand money for jobs.", "", "LEGITIMATE"),
 ("Income tax refund status can be checked on incometax.gov.in with PAN. No card details needed to track.", "", "LEGITIMATE"),
 ("Traffic challan of Rs 500 can be paid on echallan.parivahan.gov.in. Keep receipt for records.", "", "LEGITIMATE"),
 ("Jio recharge of Rs 239 successful, validity 28 days. Manage plan in MyJio app.", "", "LEGITIMATE"),
 ("Your train ticket PNR 482910 confirmed, coach B2 seat 41. Chart at 8pm. Check NTES for live status.", "", "LEGITIMATE"),
 ("Parents teacher meeting on Saturday 10am in school hall. Attendance requested for final year parents.", "", "LEGITIMATE"),
 ("Blood donation camp on Monday in auditorium 9am to 1pm. Volunteers contact NSS coordinator.", "", "LEGITIMATE"),
 ("Course certificate for Python is ready in your Coursera account under Accomplishments. Download anytime.", "", "LEGITIMATE"),
 ("Free NPTEL course enrolment open till 31 Jan on swayam.gov.in. Exam fee Rs 1000 paid only on official exam portal.", "", "LEGITIMATE"),
 ("Campus ambassador volunteering: certificate after 2 months outreach, no fee, apply on official fest website.", "", "LEGITIMATE"),
 ("Placement cell notice: beware of agents asking money for TCS roles. All drives are free via cell.", "", "LEGITIMATE"),
 ("Medicine reminder: take tablet after dinner. Next checkup on 5th at city hospital OPD.", "", "LEGITIMATE"),
 ("Weather update: heavy rain expected tomorrow, college buses may run 15 min late. Check official group.", "", "LEGITIMATE"),
 ("Cricket practice at 6am on ground. New joiners bring ID card and sports shoes.", "", "LEGITIMATE"),
 ("Canteen coupon Rs 100 received. Show QR at counter. Thank you for payment.", "", "LEGITIMATE"),
 ("Group gift share Rs 250. Send to class representative account and mark name in sheet.", "", "LEGITIMATE"),
 ("Assignment PDF for DBMS unit 3 uploaded in drive. Last date Friday, submit on Moodle.", "", "LEGITIMATE"),
 ("UPI payment of Rs 450 to canteen successful, UTR 328810. Contact bank for disputes, never share PIN.", "", "LEGITIMATE"),
 ("EPFO contribution Rs 1800 credited for October. Check passbook on official EPFO portal.", "", "LEGITIMATE"),
 ("Aadhaar PVC order Rs 50 paid on uidai.gov.in. Track with SRN in 5 working days.", "", "LEGITIMATE"),
 ("Passport appointment on 12 Dec 10:30am at PSK. Carry originals plus one photocopy set.", "", "LEGITIMATE"),
 ("Voter ID correction submitted, reference ID shared. Collect updated card from BLO office after SMS.", "", "LEGITIMATE"),
 ("Bus pass renewal Rs 800 for semester. Apply at depot counter with college bonafide and photo.", "", "LEGITIMATE"),
 ("Lab viva schedule: batch A Monday, batch B Tuesday. Syllabus covers experiments 1 to 6.", "", "LEGITIMATE"),
 ("Mess menu for week shared in hostel group. Feedback to mess secretary by Sunday evening.", "", "LEGITIMATE"),
 ("Doctor appointment confirmed Tuesday 6pm, room 12. Bring previous reports and prescription.", "", "LEGITIMATE"),
 ("Water supply maintenance Sunday 10am to 2pm in hostel block C. Store water accordingly.", "", "LEGITIMATE"),
 ("Scholarship documents verification on 18 Nov at scholarship section with originals. No fee required.", "", "LEGITIMATE"),
 ("Company webinar on safe online payments Friday 3pm. Join via official Teams link from placement cell.", "", "LEGITIMATE"),
 ("Lost ID card found near library. Collect from security desk with proof of identity.", "", "LEGITIMATE"),
 ("Fee receipt for semester 5 available on ERP. Download and keep for scholarship application.", "", "LEGITIMATE"),
 ("Alumni talk on careers in data science Saturday 11am, seminar hall. Open to all years.", "", "LEGITIMATE"),
 ("Coding club contest Sunday 7pm on HackerRank. Practice problems shared in group.", "", "LEGITIMATE"),
 ("Roommate message: bought milk and bread Rs 120, please pay your half when free.", "", "LEGITIMATE"),
 ("Mom: reached home safely, call when you finish classes. Take care and eat lunch.", "", "LEGITIMATE"),
 ("Friend: are you joining weekend trek? Bus leaves 5am from gate, Rs 900 includes food.", "", "LEGITIMATE"),
 ("Professor: office hours 3 to 5pm for doubts. Bring record book for signature.", "", "LEGITIMATE"),
 ("NSS cleaning drive Sunday 8am near lake. Gloves and bags provided by coordinators.", "", "LEGITIMATE"),
 ("Fest volunteer form is free on official site. Certificate for all volunteers after event.", "", "LEGITIMATE"),
 ("Bank statement for October available in netbanking. Review and report unknown debits to branch.", "", "LEGITIMATE"),
 ("Policy: recruiters using gmail for offers should be verified on LinkedIn and company site before responding.", "", "LEGITIMATE"),
 ("Tip: check sender domain spelling, hover links without clicking, never enter OTP on unknown pages.", "", "LEGITIMATE"),
 ("Exam timetable published on university site. Hall tickets from 1 Dec in student login.", "", "LEGITIMATE"),
 ("Holiday on Monday for local festival as per circular. Labs rescheduled to Wednesday.", "", "LEGITIMATE"),
]

def build_new_df():
    rows = []
    nid = 5000
    for text, url, cat in NEW_SCAM:
        label = 0 if cat == "LEGIT_MARKER" else 1
        category = "LEGITIMATE" if cat == "LEGIT_MARKER" else cat
        rows.append({"id": f"REAL_{nid}", "text": text, "url": url, "label": label,
                     "category": category, "source_group": f"REAL_{cat}",
                     "origin": "realistic_handwritten", "language": "en"})
        nid += 1
    for text, url, cat in NEW_LEGIT:
        rows.append({"id": f"REAL_{nid}", "text": text, "url": url, "label": 0,
                     "category": cat, "source_group": "REAL_LEGIT",
                     "origin": "realistic_handwritten", "language": "en"})
        nid += 1
    return pd.DataFrame(rows)

def main():
    df_old = pd.read_csv(BASE / "combined_examples.csv")
    print(f"Old: {len(df_old)} ({int((df_old.label==1).sum())} scam / {int((df_old.label==0).sum())} legit)")
    df_new = build_new_df()
    print(f"New realistic: {len(df_new)} ({int((df_new.label==1).sum())} scam / {int((df_new.label==0).sum())} legit)")
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    # exact-text dedup
    df_all["_k"] = df_all["text"].str.lower().str.strip()
    df_all = df_all.drop_duplicates(subset=["_k"]).drop(columns=["_k"]).reset_index(drop=True)
    print(f"Combined deduped: {len(df_all)} ({int((df_all.label==1).sum())} scam / {int((df_all.label==0).sum())} legit)")
    df_all["full_text"] = df_all["text"].fillna("") + " " + df_all["url"].fillna("")
    df_all.to_csv(BASE / "combined_examples_v2.csv", index=False)
    print("Saved combined_examples_v2.csv")

    train_df, test_df = train_test_split(df_all, test_size=0.2, random_state=42, stratify=df_all["label"])
    train_df, val_df = train_test_split(train_df, test_size=0.15, random_state=42, stratify=train_df["label"])
    print(f"Train {len(train_df)} / Val {len(val_df)} / Test {len(test_df)}")

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=15000)
    X_train = vec.fit_transform(train_df["full_text"])
    X_val = vec.transform(val_df["full_text"])
    X_test = vec.transform(test_df["full_text"])
    y_train, y_val, y_test = train_df["label"].values, val_df["label"].values, test_df["label"].values

    lr = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0, random_state=42)
    lr.fit(X_train, y_train)

    probs_val = lr.predict_proba(X_val)[:, 1]
    best_t, best_f1 = 0.5, -1
    for t in np.linspace(0.05, 0.9, 86):
        f1 = f1_score(y_val, (probs_val >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    print(f"Best threshold {best_t:.3f} val F1 {best_f1:.4f}")

    probs_test = lr.predict_proba(X_test)[:, 1]
    pred_test = (probs_test >= best_t).astype(int)
    print("=== ML TEST ===")
    print(confusion_matrix(y_test, pred_test))
    print(classification_report(y_test, pred_test, target_names=["Legitimate", "Scam"]))
    print(f"PR-AUC {average_precision_score(y_test, probs_test):.4f}")

    # Rule engine on same test sample (cap 300 for speed)
    from app.services.text_analyzer import TextAnalyzer
    from app.services.url_analyzer import analyze_urls
    analyzer = TextAnalyzer()
    samp = test_df.sample(n=min(300, len(test_df)), random_state=42)
    rule_preds = []
    for _, row in samp.iterrows():
        r = analyzer.analyze(row["text"], source="text")
        if pd.notna(row["url"]) and row["url"]:
            ur = analyze_urls([row["url"]])
            r["score"] = max(r["score"], ur.get("score", 0))
            r["indicators"].extend(ur.get("indicators", []))
        rule_preds.append(1 if r["score"] >= 30 else 0)
    print("=== RULE ENGINE (sample) ===")
    print(confusion_matrix(samp["label"].values, rule_preds))
    print(classification_report(samp["label"].values, rule_preds, target_names=["Legitimate", "Scam"]))

    # Save with backup
    model_path = BACKEND / "ml_model.joblib"
    if model_path.exists():
        shutil.copy(model_path, BACKEND / "ml_model.v1.joblib")
        print("Backed up old model to ml_model.v1.joblib")
    joblib.dump({"vectorizer": vec, "model": lr, "threshold": float(best_t), "type": "lr_v2_realistic"}, model_path)
    print(f"Saved new model vocab={len(vec.vocabulary_)} threshold={best_t:.3f}")

    fn = np.array(vec.get_feature_names_out())
    coef = lr.coef_[0]
    print("Top scam terms:", [fn[i] for i in np.argsort(coef)[-15:][::-1]])
    print("Top legit terms:", [fn[i] for i in np.argsort(coef)[:15]])

if __name__ == "__main__":
    main()
