"""v2b: balance legit + thin categories, retrain final model."""
import sys
sys.path.insert(0, r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')
import shutil
from pathlib import Path
import pandas as pd, numpy as np, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, average_precision_score, f1_score

BASE = Path(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data')
BACKEND = Path(r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')

EXTRA = [
 # thin-category scam: PHISHING (varied)
 ("Your Gmail storage is full. Confirm password on this page within 24 hours or inbox will be locked.", "http://mail-storage-full.example/verify", "PHISHING", 1),
 ("Apple ID locked due to suspicious activity. Unlock now by entering full card details and OTP.", "http://appleid-unlock-secure.example/login", "PHISHING", 1),
 ("Netflix payment failed. Update billing now via link or membership cancelled tonight.", "http://netflix-billing-update.example/pay", "PHISHING", 1),
 ("Zoom meeting invite from HR with login page asking for email password to join interview.", "http://zoom-meeting-join-hr.example/login", "PHISHING", 1),
 ("LinkedIn: your profile violates policy, confirm identity with password to avoid restriction.", "http://linkedin-verify-id.example/login", "PHISHING", 1),
 ("Whatsapp verification: forward this 6-digit code to our support agent to keep your number active.", "", "PHISHING", 1),
 ("Google Pay reward Rs 999 expired. Claim by entering UPI PIN on linked page before midnight.", "http://gpay-reward-claim.example/win", "PHISHING", 1),
 ("PhonePe cashback failed. Re-validate wallet with Aadhaar OTP on this link to release Rs 750.", "http://phonepe-wallet-check.example/kyc", "PHISHING", 1),
 ("Your PAN-Aadhaar linking failed. Click here and submit OTP to avoid Rs 1000 penalty.", "http://pan-aadhaar-link-fast.example/otp", "PHISHING", 1),
 ("EPF withdrawal of Rs 85000 approved. Enter bank credentials on this form to credit amount.", "http://epf-withdraw-claim.example/form", "PHISHING", 1),
 ("AIIMS job alert: nursing posts without exam, salary Rs 80000. Pay Rs 2000 application on WhatsApp.", "", "FAKE_JOB", 1),
 ("Railway ticket collector vacancy, 500 posts, direct selection. Send Rs 1500 exam exemption fee.", "", "FAKE_JOB", 1),
 ("ONGC apprentice with Rs 30000 stipend, no merit list. Pay Rs 999 joining kit to confirm.", "", "FAKE_INTERNSHIP", 1),
 ("NITI Aayog research intern, certificate plus Rs 25000. Registration Rs 1400 on personal UPI today.", "", "FAKE_INTERNSHIP", 1),
 ("INSPIRE scholarship Rs 80000 released. Pay Rs 1200 DST clearance and share netbanking OTP.", "", "FAKE_SCHOLARSHIP", 1),
 ("Minority scholarship approved Rs 25000. Verify by sending bank passbook photo plus Rs 500 fee.", "", "FAKE_SCHOLARSHIP", 1),
 ("Laptop scholarship for SC students: free MacBook after Rs 3000 delivery charge to courier agent.", "", "FAKE_SCHOLARSHIP", 1),
 ("Sports quota scholarship trial in Delhi, guaranteed selection after Rs 1800 ground fee in cash.", "", "FAKE_SCHOLARSHIP", 1),
 ("IIT Madras online certificate with placement, Rs 45000 value free. Pay Rs 2500 exam slot now.", "", "FAKE_TRAINING", 1),
 ("Digital marketing course, earn Rs 60000 monthly after 15 days. Advance Rs 4000 locks scholarship seat.", "", "FAKE_TRAINING", 1),
 ("Pool campus with Wipro and HCL, 300 offers. Collect Rs 1600 entry pass from student coordinator.", "", "FAKE_PLACEMENT", 1),
 ("Mega job mela entry ticket Rs 900, spot offer letter for all. Bring Aadhaar and 2 photos tomorrow.", "", "FAKE_PLACEMENT", 1),
 ("TCS offer with employee ID generated before interview. Pay Rs 5500 laptop security to receive kit.", "", "FAKE_OFFER_LETTER", 1),
 ("Deloitte consulting letter, US shift, Rs 14 LPA. Visa plus medical Rs 12000 to agent before Friday.", "", "FAKE_OFFER_LETTER", 1),
 ("YouTube subscriber task: pay Rs 3000 to upgrade to gold tasks earning Rs 9000 daily on Telegram.", "", "PAYMENT_SCAM", 1),
 ("Rent a bank account: Rs 10000 monthly for letting us use your UPI for business transfers.", "", "PAYMENT_SCAM", 1),
 ("Mule trap variation: receive Rs 50000 and forward 90 percent to next wallet, keep commission.", "", "PAYMENT_SCAM", 1),
 # legit diversity (110)
 ("Morning lab shifted to 9am, carry observation book. Attendance will be taken in first 10 minutes.", "", "LEGITIMATE", 0),
 ("Department meeting minutes shared in drive. Action items due next Wednesday noon.", "", "LEGITIMATE", 0),
 ("Sports day registrations open at gym office. Events include 100m, relay and football.", "", "LEGITIMATE", 0),
 ("Counselling session for internships Thursday 5pm, placement office room 4.", "", "LEGITIMATE", 0),
 ("GATE 2027 notification released on gate.iitk.ac.in. Apply before 7 Oct, fee Rs 2000.", "", "LEGITIMATE", 0),
 ("CAT admit card available on iimcat.ac.in. Download with login, check centre a day before.", "", "LEGITIMATE", 0),
 ("UPSC prelims result on upsc.gov.in. Check roll number PDF, mains form window opens Monday.", "", "LEGITIMATE", 0),
 ("SSC CHSL answer key challenge till 6pm on ssc.gov.in with Rs 100 per question.", "", "LEGITIMATE", 0),
 ("CBSE sample papers for class 12 on cbseacademic.nic.in. Practice with marking scheme.", "", "LEGITIMATE", 0),
 ("University transcript request: apply on ERP with Rs 500 per copy, collect after 7 days.", "", "LEGITIMATE", 0),
 ("Bonafide certificate issued in 2 working days from admin block with fee receipt.", "", "LEGITIMATE", 0),
 ("No dues form must be signed by library, hostel and accounts before final exam.", "", "LEGITIMATE", 0),
 ("Convocation gown distribution Monday 10am to 4pm at auditorium with ID card.", "", "LEGITIMATE", 0),
 ("Alumni mentorship slots booked via official form. Sessions online every second Saturday.", "", "LEGITIMATE", 0),
 ("Research paper reading group Friday: attention is all you need, room 204.", "", "LEGITIMATE", 0),
 ("DBMS quiz covers normalization till 3NF. Closed book, 30 minutes, in tutorial hall.", "", "LEGITIMATE", 0),
 ("Operating systems assignment: implement round robin scheduler in C, submit zip on Moodle.", "", "LEGITIMATE", 0),
 ("Networks lab: configure static routing on 3 routers, show output to instructor for marks.", "", "LEGITIMATE", 0),
 ("Maths tutorial sheets 5 and 6 due Tuesday. Doubts in tutorial hour only.", "", "LEGITIMATE", 0),
 ("Physics lab readings must be entered in fair record with graph and error analysis.", "", "LEGITIMATE", 0),
 ("Chemistry titration experiment Thursday. Wear apron and bring gloves from store.", "", "LEGITIMATE", 0),
 ("Workshop practice: filing and drilling job, submit finished piece for evaluation.", "", "LEGITIMATE", 0),
 ("Drawing sheets: orthographic projections of bracket, use first angle method.", "", "LEGITIMATE", 0),
 ("English presentation topics allotted roll wise. Slides due Sunday night by mail.", "", "LEGITIMATE", 0),
 ("Economics lecture covers inflation indices with RBI bulletin data for discussion.", "", "LEGITIMATE", 0),
 ("Canteen introduces millet meals Tuesday and Thursday. Feedback register at counter.", "", "LEGITIMATE", 0),
 ("Gym timings 6 to 9am and 5 to 8pm. Membership Rs 500 per semester at sports office.", "", "LEGITIMATE", 0),
 ("Swimming trials Saturday 7am. Bring cap and college ID for entry.", "", "LEGITIMATE", 0),
 ("Music club auditions in activity room Wednesday evening. Two minute piece of choice.", "", "LEGITIMATE", 0),
 ("Drama society street play rehearsal 6pm near fountain. Scripts shared in group.", "", "LEGITIMATE", 0),
 ("Photography walk Sunday 6:30am at lake gate. Carry water and permission letter.", "", "LEGITIMATE", 0),
 ("Robotics club needs volunteers for line follower build. Parts issued on returnable basis.", "", "LEGITIMATE", 0),
 ("E-cell startup meet with two founders Saturday. Register free on official fest page.", "", "LEGITIMATE", 0),
 ("Debate competition motions released a day before. Teams of two, register at literary desk.", "", "LEGITIMATE", 0),
 ("Blood group testing camp Tuesday 10am, health centre room 3, free for students.", "", "LEGITIMATE", 0),
 ("Dental checkup camp Thursday by city hospital team in seminar hall foyer.", "", "LEGITIMATE", 0),
 ("Vaccination drive for flu Saturday 9am to noon at health centre with ID.", "", "LEGITIMATE", 0),
 ("Counsellor available Monday to Friday 10am to 4pm for stress and career guidance.", "", "LEGITIMATE", 0),
 ("Anti ragging helpline and warden numbers displayed on hostel notice board.", "", "LEGITIMATE", 0),
 ("Fire drill Wednesday 11am in academic block. Assemble on playground after alarm.", "", "LEGITIMATE", 0),
 ("Lost wallet with brown cover near bus stop. Return to help desk for reward.", "", "LEGITIMATE", 0),
 ("Found set of keys near canteen. Collect from security cabin after describing keychain.", "", "LEGITIMATE", 0),
 ("Bus route 7 diverted via market due to road work this week. Delay by 10 minutes.", "", "LEGITIMATE", 0),
 ("Metro card recharge Rs 500 done at station counter. Balance valid for all lines.", "", "LEGITIMATE", 0),
 ("Post office speed post Rs 80 to home. Tracking slip kept for reference.", "", "LEGITIMATE", 0),
 ("Courier received at hostel gate. Collect with ID before 8pm today.", "", "LEGITIMATE", 0),
 ("Laundry tokens Rs 10 per cloth at shop 4. Delivery in two days with token.", "", "LEGITIMATE", 0),
 ("Haircut camp? No. Barber shop rates: Rs 80 haircut near gate market.", "", "LEGITIMATE", 0),
 ("Stationery shop: printout Rs 3 per page, spiral binding Rs 40 near library.", "", "LEGITIMATE", 0),
 ("Bank branch timings 10am to 4pm. Education loan queries at counter 5 with documents.", "", "LEGITIMATE", 0),
 ("ATM near gate dispenses cash. Never accept help from strangers while entering PIN.", "", "LEGITIMATE", 0),
 ("Credit card bill Rs 3200 due 5th. Pay via official bank app, keep autopay record.", "", "LEGITIMATE", 0),
 ("Mutual fund SIP Rs 1000 debited 1st of month. Statement in AMC app for review.", "", "LEGITIMATE", 0),
 ("Rent agreement renewal Rs 500 stamp plus notary. Both parties sign with witnesses.", "", "LEGITIMATE", 0),
 ("Electrician visit Rs 200 for fan repair in room 214. Complaint logged with warden.", "", "LEGITIMATE", 0),
 ("Plumber fixed washroom tap Tuesday. No charge as covered in maintenance.", "", "LEGITIMATE", 0),
 ("WiFi downtime Sunday 2 to 4am for maintenance. Use library LAN as backup.", "", "LEGITIMATE", 0),
 ("Password reset for ERP: use forgot link with registered email, OTP valid 10 minutes.", "", "LEGITIMATE", 0),
 ("Never reuse college password on shopping sites. Enable two step verification.", "", "LEGITIMATE", 0),
 ("Phishing drill mail from IT cell is a test. Report with report button, do not share password.", "", "LEGITIMATE", 0),
 ("Official job mail comes from company domain and lists interview panel. Verify on site.", "", "LEGITIMATE", 0),
 ("Genuine internship letter mentions mentor, duration and stipend with HR contact.", "", "LEGITIMATE", 0),
 ("Parents visiting Sunday: guest room Rs 600 per night, book at hostel office.", "", "LEGITIMATE", 0),
 ("Festival holidays list published in circular. Hostel mess runs limited menu.", "", "LEGITIMATE", 0),
 ("Scholarship helpdesk open 2 to 4pm for form errors. Bring printed application.", "", "LEGITIMATE", 0),
 ("Income certificate for EWS must be FY 2025-26 from tehsil, apply 15 days early.", "", "LEGITIMATE", 0),
 ("Caste certificate verification at SDM office with school records and affidavit.", "", "LEGITIMATE", 0),
 ("Domicile renewal needs rent agreement plus 3 year residence proof.", "", "LEGITIMATE", 0),
 ("Bonafide for passport: collect from admin with admission receipt and photo.", "", "LEGITIMATE", 0),
 ("Character certificate request via ERP, issued after mentor approval.", "", "LEGITIMATE", 0),
 ("Migration certificate needed for PG admission. Apply with degree copy and Rs 300.", "", "LEGITIMATE", 0),
 ("Degree correction: name spelling as per 10th marksheet only, submit affidavit.", "", "LEGITIMATE", 0),
 ("Back paper form Rs 1000 per subject on exam portal till 20th with late fee after.", "", "LEGITIMATE", 0),
 ("Revaluation result declared on university login. Apply for photocopy within 7 days.", "", "LEGITIMATE", 0),
 ("Summer school on AI in June, selection by CGPA and statement. Details on dept site.", "", "LEGITIMATE", 0),
 ("Winter school travel grant covers train fare with tickets and bonafide.", "", "LEGITIMATE", 0),
 ("Conference travel form needs guide signature plus acceptance mail print.", "", "LEGITIMATE", 0),
 ("Journal club paper shared: BERT pre-training, discuss evaluation section.", "", "LEGITIMATE", 0),
 ("Kaggle study group meets Sunday to solve tabular playground series.", "", "LEGITIMATE", 0),
 ("Open source sprint: fix documentation typos first, then good first issues.", "", "LEGITIMATE", 0),
 ("Leetcode contest rating improved after solving two mediums weekly.", "", "LEGITIMATE", 0),
 ("Gym trainer advises rest day after leg day. Drink water and stretch.", "", "LEGITIMATE", 0),
 ("Match score: CSE beat ECE 2-1 in football semis. Finals Friday 4pm.", "", "LEGITIMATE", 0),
 ("Yoga session 6:30am Wednesday on terrace. Mats available at sports room.", "", "LEGITIMATE", 0),
 ("Meditation workshop by counsellor Friday evening, hall B, walk in free.", "", "LEGITIMATE", 0),
 ("Book fair in library till Saturday. 20 percent discount on novels.", "", "LEGITIMATE", 0),
 ("New arrivals: data science and design books added to shelf 4.", "", "LEGITIMATE", 0),
 ("Return overdue books to avoid Rs 2 per day fine. Renew online once.", "", "LEGITIMATE", 0),
 ("Study room open till 11pm during exams with ID entry.", "", "LEGITIMATE", 0),
 ("Group study slots booked at library desk for 2 hour blocks.", "", "LEGITIMATE", 0),
 ("Printing quota 100 pages monthly. Extra at Rs 2 in computer centre.", "", "LEGITIMATE", 0),
 ("Software install request via ticket with faculty approval for lab PCs.", "", "LEGITIMATE", 0),
 ("Project guide approved dataset from UCI repository for minor project.", "", "LEGITIMATE", 0),
 ("Viva external examiner list published. Report in formals with file and model.", "", "LEGITIMATE", 0),
 ("Industrial visit to dairy plant Friday. Bus at 8am, wear shoes and ID.", "", "LEGITIMATE", 0),
 ("Guest lecture on EV batteries Monday 11am. Attendance for third year.", "", "LEGITIMATE", 0),
 ("NCC parade Sunday 7am in uniform. Absentees submit leave to officer.", "", "LEGITIMATE", 0),
 ("NSS hours updated in portal after upload of attendance sheets.", "", "LEGITIMATE", 0),
 ("Scout camp fee Rs 300 includes food. Consent form signed by parent needed.", "", "LEGITIMATE", 0),
 ("First aid box refilled in lab. Report expiry medicines to attendant.", "", "LEGITIMATE", 0),
 ("CCTV notice: corridors monitored for safety as per institute policy.", "", "LEGITIMATE", 0),
 ("Grievance box opened every Friday by committee in presence of warden.", "", "LEGITIMATE", 0),
 ("Suggestion: keep dustbins segregated for wet and dry waste on each floor.", "", "LEGITIMATE", 0),
 ("Rainwater harvesting tank cleaning Saturday. Avoid parking nearby.", "", "LEGITIMATE", 0),
 ("Solar panels output report shared by estate office for awareness.", "", "LEGITIMATE", 0),
 ("Tree plantation Sunday 8am near gate 2. Saplings and tools provided.", "", "LEGITIMATE", 0),
 ("E-waste collection box in admin lobby for old chargers and batteries.", "", "LEGITIMATE", 0),
]

def main():
    df = pd.read_csv(BASE / "combined_examples_v2.csv")
    print("v2 in:", len(df))
    rows = []
    nid = 9000
    for text, url, cat, label in EXTRA:
        rows.append({"id": f"REALB_{nid}", "text": text, "url": url, "label": label,
                     "category": cat, "source_group": f"REALB_{cat}",
                     "origin": "realistic_v2b", "language": "en"})
        nid += 1
    df2 = pd.DataFrame(rows)
    df_all = pd.concat([df, df2], ignore_index=True)
    df_all["_k"] = df_all["text"].str.lower().str.strip()
    df_all = df_all.drop_duplicates(subset=["_k"]).drop(columns=["_k"]).reset_index(drop=True)
    print("v2b total:", len(df_all), df_all["label"].value_counts().to_dict())
    print(df_all["category"].value_counts())
    df_all["full_text"] = df_all["text"].fillna("") + " " + df_all["url"].fillna("")
    df_all.to_csv(BASE / "combined_examples_v3.csv", index=False)

    train_df, test_df = train_test_split(df_all, test_size=0.2, random_state=42, stratify=df_all["label"])
    train_df, val_df = train_test_split(train_df, test_size=0.15, random_state=42, stratify=train_df["label"])
    print(f"Train {len(train_df)} / Val {len(val_df)} / Test {len(test_df)}")
    vec = TfidfVectorizer(ngram_range=(1,2), min_df=2, sublinear_tf=True, max_features=15000)
    X_train = vec.fit_transform(train_df["full_text"])
    X_val = vec.transform(val_df["full_text"])
    X_test = vec.transform(test_df["full_text"])
    y_train, y_val, y_test = train_df["label"].values, val_df["label"].values, test_df["label"].values
    lr = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0, random_state=42)
    lr.fit(X_train, y_train)
    pv = lr.predict_proba(X_val)[:, 1]
    best_t, best_f1 = 0.5, -1
    for t in np.linspace(0.05, 0.9, 86):
        f1 = f1_score(y_val, (pv >= t).astype(int), zero_division=0)
        if f1 > best_f1: best_f1, best_t = f1, t
    print(f"Best thr {best_t:.3f} val F1 {best_f1:.4f}")
    pt = lr.predict_proba(X_test)[:, 1]
    pred = (pt >= best_t).astype(int)
    print(confusion_matrix(y_test, pred))
    print(classification_report(y_test, pred, target_names=["Legitimate","Scam"]))
    print(f"PR-AUC {average_precision_score(y_test, pt):.4f}")
    shutil.copy(BACKEND / "ml_model.joblib", BACKEND / "ml_model.v2a.joblib")
    joblib.dump({"vectorizer": vec, "model": lr, "threshold": float(best_t), "type": "lr_v3_realistic_balanced"}, BACKEND / "ml_model.joblib")
    print(f"Saved final vocab={len(vec.vocabulary_)} thr={best_t:.3f}")

if __name__ == "__main__":
    main()
