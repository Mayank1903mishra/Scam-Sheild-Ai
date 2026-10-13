"""Quick train ML model on rule-engine scored data."""
import sys
sys.path.insert(0, r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend')

import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, confusion_matrix, average_precision_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from app.services.text_analyzer import TextAnalyzer

# Load the combined dataset
df = pd.read_csv(r'C:\Users\mayank\Downloads\scamshield_dataset_kit\scamshield_dataset_kit\data\combined_examples.csv')
print(f"Loaded {len(df)} examples: {df.label.sum()} scam, {(df.label==0).sum()} legitimate")

# Use text analyzer directly (faster than full input_manager)
analyzer = TextAnalyzer()

# Score a sample first to verify
print("Scoring sample with rule engine...")
sample = df.sample(n=200, random_state=42)
rule_scores = []
for _, row in sample.iterrows():
    text = row['text']
    url = row['url'] if pd.notna(row['url']) else ""
    result = analyzer.analyze(text, source="text")
    if url:
        from app.services.url_analyzer import analyze_urls
        url_result = analyze_urls([url])
        result['score'] = max(result['score'], url_result.get('score', 0))
        result['indicators'].extend(url_result.get('indicators', []))
    rule_scores.append(result['score'])

sample['rule_score'] = rule_scores
print(f"Rule score range: {sample['rule_score'].min()} - {sample['rule_score'].max()}")
print(f"Mean rule score (scam): {sample[sample.label==1]['rule_score'].mean():.1f}")
print(f"Mean rule score (legit): {sample[sample.label==0]['rule_score'].mean():.1f}")

# Now train ML model on FULL dataset using rule scores as soft labels
# But also use true labels for supervised training
print("\nTraining ML models...")

# Prepare text features
df['full_text'] = df['text'].fillna('') + ' ' + df['url'].fillna('')

# Split
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])
train_df, val_df = train_test_split(train_df, test_size=0.15, random_state=42, stratify=train_df['label'])

print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

# TF-IDF
vec = TfidfVectorizer(ngram_range=(1,2), min_df=2, sublinear_tf=True, max_features=10000)
X_train = vec.fit_transform(train_df['full_text'])
X_val = vec.transform(val_df['full_text'])
X_test = vec.transform(test_df['full_text'])

y_train = train_df['label'].values
y_val = val_df['label'].values
y_test = test_df['label'].values

# Train Logistic Regression
lr = LogisticRegression(max_iter=2000, class_weight='balanced', C=1.0, random_state=42)
lr.fit(X_train, y_train)

# Train SVM
svm = LinearSVC(class_weight='balanced', max_iter=5000, random_state=42)
svm.fit(X_train, y_train)

# Evaluate on validation to pick threshold
lr_val_probs = lr.predict_proba(X_val)[:, 1]
svm_val_scores = svm.decision_function(X_val)

# Find best threshold on validation (F1)
best_thresh_lr = 0.5
best_f1_lr = 0
for t in np.linspace(0.1, 0.9, 81):
    pred = (lr_val_probs >= t).astype(int)
    from sklearn.metrics import f1_score
    f1 = f1_score(y_val, pred, zero_division=0)
    if f1 > best_f1_lr:
        best_f1_lr = f1
        best_thresh_lr = t

best_thresh_svm = 0
best_f1_svm = 0
for t in np.linspace(svm_val_scores.min(), svm_val_scores.max(), 81):
    pred = (svm_val_scores >= t).astype(int)
    from sklearn.metrics import f1_score
    f1 = f1_score(y_val, pred, zero_division=0)
    if f1 > best_f1_svm:
        best_f1_svm = f1
        best_thresh_svm = t

print(f"\nBest LR threshold: {best_thresh_lr:.3f} (val F1: {best_f1_lr:.3f})")
print(f"Best SVM threshold: {best_thresh_svm:.3f} (val F1: {best_f1_svm:.3f})")

# Test evaluation
lr_test_probs = lr.predict_proba(X_test)[:, 1]
svm_test_scores = svm.decision_function(X_test)

lr_test_pred = (lr_test_probs >= best_thresh_lr).astype(int)
svm_test_pred = (svm_test_scores >= best_thresh_svm).astype(int)

print("\n=== TEST RESULTS ===")
print("\n--- Logistic Regression ---")
print(confusion_matrix(y_test, lr_test_pred))
print(classification_report(y_test, lr_test_pred, target_names=['Legitimate', 'Scam']))
print(f"PR-AUC: {average_precision_score(y_test, lr_test_probs):.4f}")

print("\n--- Linear SVM ---")
print(confusion_matrix(y_test, svm_test_pred))
print(classification_report(y_test, svm_test_pred, target_names=['Legitimate', 'Scam']))
print(f"PR-AUC: {average_precision_score(y_test, (svm_test_scores - svm_test_scores.min()) / (svm_test_scores.max() - svm_test_scores.min() + 1e-8)):.4f}")

# Also evaluate rule engine on test set
print("\n--- Rule Engine (on test set) ---")
test_rule_scores = []
for _, row in test_df.iterrows():
    text = row['text']
    url = row['url'] if pd.notna(row['url']) else ""
    result = analyzer.analyze(text, source="text")
    if url:
        from app.services.url_analyzer import analyze_urls
        url_result = analyze_urls([url])
        result['score'] = max(result['score'], url_result.get('score', 0))
    test_rule_scores.append(result['score'])

rule_test_pred = (np.array(test_rule_scores) >= 30).astype(int)
print(confusion_matrix(y_test, rule_test_pred))
print(classification_report(y_test, rule_test_pred, target_names=['Legitimate', 'Scam']))

# Save best model
best_model = {'vectorizer': vec, 'model': lr, 'threshold': best_thresh_lr, 'type': 'lr'}
joblib.dump(best_model, r'C:\Users\mayank\OneDrive\Documents\Desktop\scam sheild Ai\backend\ml_model.joblib')
print("\nSaved ML model to backend/ml_model.joblib")

# Top features
fn = np.array(vec.get_feature_names_out())
coef = lr.coef_[0]
top_scam_idx = np.argsort(coef)[-30:][::-1]
top_legit_idx = np.argsort(coef)[:30]
print("\nTop scam indicators:")
for i in top_scam_idx:
    print(f"  {fn[i]}: {coef[i]:.3f}")
print("\nTop legitimate indicators:")
for i in top_legit_idx:
    print(f"  {fn[i]}: {coef[i]:.3f}")