#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import random

def normalize_text(text):
    """Normalize text for comparison by trimming and standardizing case"""
    if not isinstance(text, str):
        return str(text)
    return text.strip()

def generate_options(correct, pool=None, count=3):
    """Generate multiple choice options ensuring no duplicates."""
    # Normalize the correct answer for comparison
    correct_normalized = normalize_text(correct)
    
    if pool:
        # Filter out the correct answer with normalization
        distractors = []
        for option in pool:
            option_normalized = normalize_text(option)
            if option_normalized != correct_normalized:
                distractors.append(option)
        
        # Ensure we have enough distractors
        if len(distractors) < count:
            print(f"Warning: Only {len(distractors)} unique distractors available for '{correct}', "
                  f"need {count}. Generating fallback options.")
            # Add fallback options if pool is too small
            fallback_count = count - len(distractors)
            fallback_start = len(distractors) + 1
            fallback_options = [f"Option {fallback_start + i}" for i in range(fallback_count)]
            distractors.extend(fallback_options)
        
        # Select unique distractors
        selected_distractors = random.sample(distractors, min(count, len(distractors)))
    else:
        # Fallback generic distractors for fields without pool
        selected_distractors = [f"Unknown {i}" for i in range(1, count+1)]
    
    # Combine correct answer with distractors
    options = [correct] + selected_distractors
    
    # Final validation: ensure all options are unique
    unique_options = []
    seen = set()
    
    for option in options:
        option_normalized = normalize_text(option)
        if option_normalized not in seen:
            unique_options.append(option)
            seen.add(option_normalized)
        else:
            # If we encounter a duplicate, try to find a replacement
            if pool:
                # Try to find another unique option from the pool
                for replacement in pool:
                    replacement_normalized = normalize_text(replacement)
                    if (replacement_normalized != option_normalized and 
                        replacement_normalized not in seen):
                        unique_options.append(replacement)
                        seen.add(replacement_normalized)
                        break
    
    # Shuffle the final options
    random.shuffle(unique_options)
    return unique_options

def run_tests():
    """Run comprehensive tests for the duplicate prevention fix"""
    print("🧪 Testing Duplicate Answer Prevention Fix")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Basic case with duplicates in pool
    print("Test 1: Basic case with duplicates")
    correct = "Pyro"
    pool = ["Pyro", "Hydro", "Electro", "Anemo", "Geo"]
    options = generate_options(correct, pool, 3)
    
    is_unique = len(options) == len(set(options))
    contains_correct = correct in options
    
    print(f"  Correct answer: {correct}")
    print(f"  Options: {options}")
    print(f"  All unique: {'✅' if is_unique else '❌'} {is_unique}")
    print(f"  Contains correct: {'✅' if contains_correct else '❌'} {contains_correct}")
    
    if not (is_unique and contains_correct):
        all_passed = False
    print()
    
    # Test 2: Case sensitivity issue
    print("Test 2: Case sensitivity handling")
    correct = "pyro"  # lowercase
    pool = ["Pyro", "Hydro", "Electro"]  # different case
    options = generate_options(correct, pool, 2)
    
    is_unique = len(options) == len(set(options))
    contains_correct = correct in options
    
    print(f"  Correct answer: {correct}")
    print(f"  Options: {options}")
    print(f"  All unique: {'✅' if is_unique else '❌'} {is_unique}")
    print(f"  Contains correct: {'✅' if contains_correct else '❌'} {contains_correct}")
    
    if not (is_unique and contains_correct):
        all_passed = False
    print()
    
    # Test 3: Small pool (insufficient distractors)
    print("Test 3: Small pool with fallback generation")
    correct = "Sword"
    pool = ["Sword", "Claymore"]  # Only 1 distractor available
    options = generate_options(correct, pool, 3)  # Need 3 distractors
    
    is_unique = len(options) == len(set(options))
    contains_correct = correct in options
    
    print(f"  Correct answer: {correct}")
    print(f"  Options: {options}")
    print(f"  All unique: {'✅' if is_unique else '❌'} {is_unique}")
    print(f"  Contains correct: {'✅' if contains_correct else '❌'} {contains_correct}")
    
    if not (is_unique and contains_correct):
        all_passed = False
    print()
    
    # Test 4: Whitespace handling
    print("Test 4: Whitespace in answers")
    correct = " Pyro "  # with spaces
    pool = ["Pyro", "Hydro", "Electro"]
    options = generate_options(correct, pool, 2)
    
    is_unique = len(options) == len(set(options))
    contains_correct = correct in options
    
    print(f"  Correct answer: '{correct}'")
    print(f"  Options: {options}")
    print(f"  All unique: {'✅' if is_unique else '❌'} {is_unique}")
    print(f"  Contains correct: {'✅' if contains_correct else '❌'} {contains_correct}")
    
    if not (is_unique and contains_correct):
        all_passed = False
    print()
    
    # Test 5: Multiple identical entries in pool
    print("Test 5: Pool with duplicate entries")
    correct = "Hydro"
    pool = ["Hydro", "Pyro", "Hydro", "Electro", "Hydro"]  # Multiple Hydro entries
    options = generate_options(correct, pool, 2)
    
    is_unique = len(options) == len(set(options))
    contains_correct = correct in options
    
    print(f"  Correct answer: {correct}")
    print(f"  Pool: {pool}")
    print(f"  Options: {options}")
    print(f"  All unique: {'✅' if is_unique else '❌'} {is_unique}")
    print(f"  Contains correct: {'✅' if contains_correct else '❌'} {contains_correct}")
    
    if not (is_unique and contains_correct):
        all_passed = False
    print()
    
    # Summary
    print("=" * 50)
    if all_passed:
        print("🎉 All tests PASSED! The fix successfully prevents duplicate answers.")
    else:
        print("❌ Some tests FAILED! The fix needs more work.")
    
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
