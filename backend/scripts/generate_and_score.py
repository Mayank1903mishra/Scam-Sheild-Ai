"""Generate larger synthetic dataset, score with rule engine, train ML model."""
import sys
sys.path.insert(0, r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')

import json
import random
import pandas as pd
import numpy as np
from app.services.input_manager import analyze_input
from app.services.text_analyzer import TextAnalyzer

# Load existing seed data
seed_df = pd.read_csv(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data\seed_examples.csv')

# Templates for generating variations
scam_templates = {
    'FAKE_INTERNSHIP': [
        "Congratulations! You are selected for a {duration} {type} internship at {company}. Pay Rs {amount} registration fee today to confirm your seat, no interview needed.",
        "Your internship is confirmed. Transfer Rs {amount} as security deposit to UPI id {upi} and send the screenshot. Offer expires in {hours} hours.",
        "Selected for {role} internship with stipend Rs {stipend}/month. Complete verification by paying Rs {amount} processing charges, refundable after joining.",
        "Dear student, your application was shortlisted automatically. To receive the internship certificate and letter, pay the onboarding fee now. Limited seats.",
    ],
    'FAKE_JOB': [
        "Hiring freshers! Work from home, earn Rs {salary} per month, no experience needed. Direct joining, pay Rs {amount} for ID card and laptop kit.",
        "HR Desk: you are selected for {role} role at {salary} without interview. Share your Aadhaar and bank details to process the joining.",
        "Part-time job: like and review videos, earn Rs {daily} daily. Join our Telegram group and deposit Rs {amount} to activate your account.",
        "Urgent vacancy, {posts} posts. Salary Rs {salary}. Send Rs {amount} refundable registration to confirm your slot, offer valid today only.",
    ],
    'FAKE_OFFER_LETTER': [
        "Offer letter attached. Position: {role}, CTC {salary}. Your joining is confirmed after payment of Rs {amount} document verification fee. Contact {email}",
        "We are pleased to offer you a role at {company}. Sign and return with Rs {amount} background check charges. Reply from the email on this letter only.",
        "Appointment letter: salary {salary}, no interview round. Kindly deposit Rs {amount} as training bond to the account below within 24 hours.",
        "Offer of employment. Report on {day}. Medical and uniform charges of Rs {amount} must be paid in advance to the HR officer's personal account.",
    ],
    'FAKE_SCHOLARSHIP': [
        "You have won a national merit scholarship of Rs {amount}. Pay Rs {fee} processing fee and share your bank login to receive the amount.",
        "Scholarship alert: claim your government grant now. Click the link and enter your net banking password to verify eligibility.",
        "Your scholarship is approved. To release funds, send Rs {fee} tax clearance to the account given. Last date today.",
        "Congratulations, selected for the international student award worth {usd} USD. Provide your OTP and card number to confirm.",
    ],
    'FAKE_AMBASSADOR': [
        "Become a college ambassador of {brand}. Earn Rs {salary} monthly. Pay Rs {amount} for ambassador kit and ID to activate your profile.",
        "Campus ambassador program: free internship certificate after you refer {ref} students. First pay Rs {amount} membership fee to join.",
        "You are chosen as brand ambassador. Share your Instagram password so our team can verify followers and start your rewards.",
        "Ambassador selection complete. Deposit Rs {amount} refundable security amount; slots are filling fast, pay in the next hour.",
    ],
    'FAKE_TRAINING': [
        "Guaranteed placement after our {days}-day {course} course. Enroll today for Rs {amount}, certificate and job assured in top MNC or full refund.",
        "Limited offer: 100% job guarantee training. Pay Rs {amount} now to lock the batch, only {seats} seats left.",
        "Get certified in {course} in {days} days. Pay the exam fee Rs {amount} to our personal UPI and receive a government-recognised certificate.",
        "Free workshop but certificate costs Rs {amount}. Pay immediately, certificate and job referral will be sent on WhatsApp.",
    ],
    'FAKE_PLACEMENT': [
        "Campus placement drive, direct hiring by {companies} MNCs. Register with Rs {amount} fee on the form link today, urgent, no spot registration.",
        "Placement cell notice: your name is in the final list. To release your offer pay Rs {amount} to the coordinator personally.",
        "Walk-in drive tomorrow, guaranteed selection for all. Transfer Rs {amount} token amount to reserve your interview slot.",
        "Recruitment update: pay the processing fee Rs {amount} to HR on this number before 6 pm to remain in the shortlisted list.",
    ],
    'PHISHING': [
        "Your {portal} account will be suspended. Verify now to keep access.",  # with URL
        "Dear user, your {service} account needs KYC. Click the link and enter your password and OTP.",  # with URL
        "Security alert: unusual sign-in to your {service}. Reset your password immediately.",  # with URL
        "Your internship certificate is ready. Download it and sign in with your university credentials.",  # with URL
    ],
    'PAYMENT_SCAM': [
        "Pay Rs {amount} to this UPI id to unlock your refund of Rs {refund}. Offer expires in {minutes} minutes.",
        "Send Rs {amount} to receive a cashback reward of Rs {reward}. Scan this QR code and enter your UPI PIN to receive money.",
        "I accidentally sent you Rs {sent}. Please return Rs {return} to my number urgently, my account will be blocked otherwise.",
        "Your parcel is held. Pay Rs {amount} customs fee at this link and enter your card details to release it.",
    ],
}

legitimate_templates = [
    "The Training and Placement Cell invites applications for summer internships. Apply through the college portal by {date}. No registration fee is charged by the company.",
    "Your application for {role} Intern was received. We will contact you from our official careers address for an interview next week.",
    "Offer letter: {role}, joining on {date}. Please accept through the official candidate portal. The company does not charge any fee at any stage.",
    "Interview invite: your technical round is on {day} {time} on the company's video platform. Carry your resume and college ID.",
    "Scholarship results: the state scholarship portal has published the merit list. Check your status on the official website using your application number.",
    "We are hiring campus ambassadors. Role is voluntary with a certificate, no payment required. Apply on our official website form.",
    "Join the free online course offered by our university. Enrol using your student login; the certification exam fee is paid on the official exam portal.",
    "Placement drive on {date} at the seminar hall. Bring three resume copies. Registration is through the placement cell, no charge.",
    "Thank you for applying. Your profile is under review and we will update you within two weeks.",
    "Reminder: semester examination fee of Rs {amount} is due by {date}. Pay on the college ERP portal; offline payments are not accepted.",
    "Your hostel fee receipt for this semester is available in the student portal. Contact the accounts office for corrections.",
    "Last date to submit scholarship documents is {day}. Upload them on the official portal; urgent corrections need the department head's sign.",
    "Passport application: please pay the government fee of Rs {amount} on the official passport website and keep the receipt.",
    "The library fine of Rs {amount} can be paid at the counter. Show your ID card.",
    "Course registration closes tonight at 11:59 pm. Log in to the university portal to confirm your electives.",
    "Your course certificate is available. Download it from your account on the platform where you enrolled.",
    "Hackathon registration is free for students. Teams of four, last date is {date}.",
    "Urgent: submit your internship report to the department by {day}, as per the circular.",
    "Never share your OTP or UPI PIN with anyone. Banks never ask for it on call or message.",
    "Beware of fake internship offers that ask for a registration fee. Genuine companies do not charge students to hire them.",
    "Cyber cell advisory: do not click unknown links claiming scholarship or refund. Report fraud at the official helpline.",
    "Please verify any offer letter with the company's official website before paying anything.",
    "College notice: students are warned against placement agents demanding money. Contact the placement cell for help.",
    "If you receive a message asking for payment to confirm a job, ignore it and report it.",
    "Our bank will never ask you to click a link to update KYC. Visit your branch or the official app.",
    "Phishing awareness session on {day}, {time} in the auditorium, all students welcome.",
    "Tip: check the sender's domain on any recruiter e-mail; free-mail addresses are a warning sign.",
    "Hey, are you coming for the project meeting at {time}? Bring your laptop.",
    "Notes for tomorrow's lecture are uploaded in the shared drive.",
    "Happy birthday! Let's go for lunch after the exam.",
    "Can you send me the assignment PDF? I lost the link.",
    "The seminar on machine learning is shifted to room {room}.",
    "Your order has been shipped and will arrive on {day}. Track it in the official app.",
    "Congratulations on getting selected for the college cricket team! Practice starts {day}.",
    "Payment of Rs {amount} received for the canteen coupon. Thank you.",
    "Please pay your share of Rs {amount} for the group gift via the class UPI, thanks!",
]

# Fill values for templates
fill_values = {
    'duration': ['2-month', '3-month', '6-month', 'summer', 'winter'],
    'type': ['remote', 'on-site', 'hybrid', 'virtual', 'work-from-home'],
    'company': ['TechNova', 'GlobalSoft', 'DataCorp', 'InfoSys', 'TechMahindra', 'Wipro', 'TCS', 'Accenture'],
    'amount': ['999', '1500', '499', '2000', '3500', '5000', '750', '1200', '2500', '6000'],
    'upi': ['hr.technova@upi', 'careers.globalsft@upi', 'placements.datacorp@upi', 'hr.infosys@upi'],
    'hours': ['2', '4', '6', '12', '24'],
    'role': ['Data Science', 'Software Engineer', 'Marketing', 'Business Analyst', 'Product Manager', 'DevOps', 'Full Stack Developer'],
    'stipend': ['15000', '20000', '25000', '30000', '35000', '40000'],
    'salary': ['45000', '50000', '60000', '75000', '90000', '120000', '1400000', '9 LPA', '12 LPA', '14 LPA'],
    'daily': ['1000', '2000', '3000', '5000', '10000'],
    'posts': ['20', '30', '50', '100', '200'],
    'email': ['hr.careers@mail-gmail.example', 'jobs@company-gmail.example', 'recruitment@fake-corp.example'],
    'day': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    'fee': ['300', '500', '750', '1000', '1500'],
    'usd': ['500', '1000', '2000', '5000', '10000'],
    'brand': ['EduSpark', 'SkillBridge', 'CareerLaunch', 'JobReady', 'PlacementPro'],
    'ref': ['5', '10', '15', '20'],
    'days': ['7', '14', '30', '45', '60'],
    'course': ['AI', 'Data Science', 'Cyber Security', 'Full Stack', 'Cloud Computing', 'DevOps', 'Machine Learning'],
    'seats': ['3', '5', '10', '15'],
    'companies': ['5', '10', '15', '20'],
    'minutes': ['5', '10', '15', '30'],
    'refund': ['5000', '10000', '15000', '20000'],
    'reward': ['5000', '10000', '20000', '50000'],
    'sent': ['5000', '8000', '10000', '20000'],
    'return': ['3000', '5000', '7000', '10000'],
    'portal': ['student portal', 'university portal', 'college portal', 'scholarship portal'],
    'service': ['college email', 'university account', 'scholarship account', 'banking portal'],
    'date': ['25 October', '15 November', '30 November', '15 December', '31 December'],
    'time': ['10 am', '11 am', '2 pm', '3 pm', '4 pm'],
    'room': ['201', '204', '301', '101', 'Auditorium'],
}

phishing_urls = [
    "http://portal-login.verify-account.example",
    "http://kyc-update.secure-bank.example",
    "http://mail-reset.example/login",
    "http://certificate-download.example",
    "http://scholarship-verify.fake-gov.example",
    "http://job-portal-fake.example/apply",
    "http://internship-confirm.example/verify",
    "http://placement-drive.example/register",
]

def fill_template(template, category):
    """Fill a template with random values."""
    text = template
    for key, values in fill_values.items():
        placeholder = '{' + key + '}'
        if placeholder in text:
            text = text.replace(placeholder, random.choice(values))
    return text

def generate_dataset(n_scam_per_cat=50, n_legitimate=200):
    """Generate a larger synthetic dataset."""
    rows = []
    id_counter = 1000
    
    # Generate scam examples
    for category, templates in scam_templates.items():
        for i in range(n_scam_per_cat):
            template = random.choice(templates)
            text = fill_template(template, category)
            
            url = ""
            if category == 'PHISHING':
                url = random.choice(phishing_urls)
            
            source_group = f"{category}_{i // 5}"
            rows.append({
                'id': f'GEN_{id_counter:04d}',
                'text': text,
                'url': url,
                'label': 1,
                'category': category,
                'source_group': source_group,
                'origin': 'synthetic_generated',
                'language': 'en'
            })
            id_counter += 1
    
    # Generate legitimate examples
    for i in range(n_legitimate):
        template = random.choice(legitimate_templates)
        text = fill_template(template, 'LEGITIMATE')
        
        rows.append({
            'id': f'GEN_{id_counter:04d}',
            'text': text,
            'url': '',
            'label': 0,
            'category': 'LEGITIMATE',
            'source_group': f'LEGIT_{i // 5}',
            'origin': 'synthetic_generated',
            'language': 'en'
        })
        id_counter += 1
    
    return pd.DataFrame(rows)

# Generate larger dataset
print("Generating larger synthetic dataset...")
gen_df = generate_dataset(n_scam_per_cat=80, n_legitimate=400)
print(f"Generated {len(gen_df)} examples: {gen_df.label.sum()} scam, {(gen_df.label==0).sum()} legitimate")

# Combine with original seed data
combined_df = pd.concat([seed_df, gen_df], ignore_index=True)
print(f"Combined: {len(combined_df)} examples")

# Save combined dataset
combined_df.to_csv(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data\combined_examples.csv', index=False)
print("Saved to combined_examples.csv")

# Now score with rule engine
print("\nScoring with rule engine...")
analyzer = TextAnalyzer()

results = []
for _, row in combined_df.iterrows():
    url_val = row['url']
    if pd.isna(url_val):
        url_val = None
    result = analyze_input(text=row['text'], url=url_val)
    results.append({
        'id': row['id'],
        'rule_score': result.risk_score,
        'rule_band': result.risk_band,
        'rule_category': result.category,
        'true_label': row['label'],
        'true_category': row['category']
    })
    if len(results) % 100 == 0:
        print(f"  Scored {len(results)}/{len(combined_df)}...")

results_df = pd.DataFrame(results)
results_df.to_csv(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data\rule_scores.csv', index=False)
print("Saved rule_scores.csv")

# Show confusion
from sklearn.metrics import confusion_matrix, classification_report
y_true = results_df['true_label']
y_pred = (results_df['rule_score'] >= 30).astype(int)  # threshold at MODERATE
print("\nRule engine performance (threshold=30):")
print(confusion_matrix(y_true, y_pred))
print(classification_report(y_true, y_pred, target_names=['Legitimate', 'Scam']))