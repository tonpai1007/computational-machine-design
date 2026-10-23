with open('reporting/generator.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix 1: HTML KPI - result.min_yield_safety_factor
text = text.replace(
    'result.min_yield_safety_factor:.2f</div>',
    'result.min_yield_safety_factor:.2f</div> if result.min_yield_safety_factor is not None else "N/A</div>"'
)

# Fix 2: HTML KPI - model.constraints.min_yield_safety_factor
text = text.replace(
    'model.constraints.min_yield_safety_factor:.2f</div>',
    'model.constraints.min_yield_safety_factor:.2f</div> if model.constraints.min_yield_safety_factor is not None else "N/A</div>"'
)

# Fix 3: HTML fatigue - result.min_fatigue_safety_factor
text = text.replace(
    'result.min_fatigue_safety_factor:.2f</div>',
    'result.min_fatigue_safety_factor:.2f</div> if result.min_fatigue_safety_factor is not None else "N/A</div>"'
)

# Fix 4: Markdown report - Yield Safety Factor line
text = text.replace(
    '| **Yield Safety Factor** | {result.min_yield_safety_factor:.2f} |',
    '| **Yield Safety Factor** | {result.min_yield_safety_factor:.2f} | N/A |'
)

# Fix 5: Markdown report - Fatigue Safety Factor line  
text = text.replace(
    '| **Fatigue Safety Factor (Goodman)** | {result.min_fatigue_safety_factor:.2f} |',
    '| **Fatigue Safety Factor (Goodman)** | {result.min_fatigue_safety_factor:.2f} | N/A |'
)

with open('reporting/generator.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed generator.py")