from app.services.input_manager import analyze_input

# Test scam
result = analyze_input(text='Congratulations! You are selected for internship. Pay Rs 999 registration fee today.', url='')
print(f'Score: {result.risk_score}, Band: {result.risk_band}, Category: {result.category}')
print(f'Module scores: {result.module_scores}')
print(f'Mode: {result.mode}')
print('Evidence:')
for e in result.evidence:
    print(f'  {e["id"]}: weight={e["weight"]}, source={e["source"]}, reason={e["reason"][:60]}')

print()

# Test legitimate
result2 = analyze_input(text='Your application for Data Analyst Intern was received. We will contact you from our official careers address for an interview next week.', url='')
print(f'Score: {result2.risk_score}, Band: {result2.risk_band}, Category: {result2.category}')
print(f'Module scores: {result2.module_scores}')
print('Evidence:')
for e in result2.evidence:
    print(f'  {e["id"]}: weight={e["weight"]}, source={e["source"]}, reason={e["reason"][:60]}')