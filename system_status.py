#!/usr/bin/env python
"""
VoxNav System Status Report
"""

import sys
import os
from datetime import datetime

def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    return version.major == 3 and version.minor >= 8

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'transformers', 'torch', 'torchaudio', 'librosa', 
        'soundfile', 'google-generativeai'
    ]
    
    installed = []
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            installed.append(package)
        except ImportError:
            missing.append(package)
    
    return installed, missing

def check_model_files():
    """Check if ASR model files exist"""
    model_path = "hindi_models/whisper-medium-hi_alldata_multigpu"
    files_to_check = [
        "config.json",
        "pytorch_model.bin", 
        "tokenizer_config.json",
        "vocab.json"
    ]
    
    found = []
    missing = []
    
    if not os.path.exists(model_path):
        return [], files_to_check, False
    
    for file in files_to_check:
        if os.path.exists(os.path.join(model_path, file)):
            found.append(file)
        else:
            missing.append(file)
    
    return found, missing, True

def check_api_keys():
    """Check if required API keys are set"""
    keys = {
        'OPENROUTER_API_KEY': os.environ.get('OPENROUTER_API_KEY', ''),
        'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY', '')
    }
    return keys

def main():
    print("📊 VoxNav System Status Report")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Python Version
    print("1. Python Environment")
    if check_python_version():
        print("   ✅ Python version compatible (3.8+)")
        print(f"   🐍 Version: {sys.version}")
    else:
        print("   ❌ Python version too old (requires 3.8+)")
        return
    
    # 2. Dependencies
    print("\n2. Dependencies Check")
    installed, missing = check_dependencies()
    print(f"   ✅ Installed ({len(installed)}): {', '.join(installed)}")
    if missing:
        print(f"   ❌ Missing ({len(missing)}): {', '.join(missing)}")
    else:
        print("   ✅ All required dependencies installed")
    
    # 3. Model Files
    print("\n3. ASR Model Check")
    found, missing_files, model_dir_exists = check_model_files()
    if not model_dir_exists:
        print("   ⚠️  Model directory not found")
        print("   💡 Download model from: https://indicwhisper.objectstore.e2enetworks.net/hindi_models.zip")
    else:
        print(f"   ✅ Model directory exists")
        print(f"   ✅ Found files ({len(found)}): {', '.join(found) if found else 'None'}")
        if missing_files:
            print(f"   ⚠️  Missing files ({len(missing_files)}): {', '.join(missing_files)}")
    
    # 4. API Keys
    print("\n4. API Keys")
    api_keys = check_api_keys()
    for key, value in api_keys.items():
        if value:
            print(f"   ✅ {key}: Set (first 8 chars: {value[:8]}...)")
        else:
            print(f"   ⚠️  {key}: Not set")
    
    # 5. Component Tests
    print("\n5. Component Functionality")
    
    # Language detection
    try:
        from core.multilingual import MultilingualHandler
        handler = MultilingualHandler()
        test_text = "नमस्ते"
        result = handler.detect_language(test_text)
        print(f"   ✅ Language detection: '{test_text}' → {result.primary_language.value}")
    except Exception as e:
        print(f"   ❌ Language detection failed: {e}")
    
    # Configuration
    try:
        from config import config
        print(f"   ✅ Configuration loading: {len(config.asr.supported_languages)} languages supported")
    except Exception as e:
        print(f"   ❌ Configuration loading failed: {e}")
    
    # Orchestrator
    try:
        os.environ["OPENROUTER_API_KEY"] = "test"  # Mock key for init test
        from core import VoxNavOrchestrator
        voxnav = VoxNavOrchestrator(lazy_load=True)
        print("   ✅ Orchestrator initialization: Success")
    except Exception as e:
        print(f"   ❌ Orchestrator initialization failed: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SYSTEM STATUS SUMMARY")
    print("=" * 60)
    
    total_checks = 7
    passed_checks = 0
    
    # Count passed checks
    if check_python_version(): passed_checks += 1
    if not missing: passed_checks += 1
    if model_dir_exists: passed_checks += 1
    if any(api_keys.values()): passed_checks += 1
    
    # Component tests (3 checks)
    component_checks = 3
    try:
        handler = MultilingualHandler()
        passed_checks += 1
        component_checks -= 1
    except: pass
    
    try:
        from config import config
        passed_checks += 1
        component_checks -= 1
    except: pass
    
    try:
        voxnav = VoxNavOrchestrator(lazy_load=True)
        passed_checks += 1
        component_checks -= 1
    except: pass
    
    print(f"✅ Passed: {passed_checks}/{total_checks + component_checks}")
    print(f"⚠️  Warnings: {total_checks + component_checks - passed_checks}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if missing:
        print("1. Install missing dependencies:")
        print("   pip install " + " ".join(missing))
    
    if not model_dir_exists:
        print("2. Download ASR model:")
        print("   mkdir -p hindi_models")
        print("   # Download from AI4Bharat website")
    
    if not any(api_keys.values()):
        print("3. Set API keys:")
        print("   $env:OPENROUTER_API_KEY = 'your-key-here'")
    
    print("4. Run full test:")
    print("   python examples.py")
    
    print("\n🎯 CURRENT STATUS:")
    if passed_checks >= 6:
        print("   🟢 System is ready for basic testing")
        print("   🟡 Full functionality requires API keys and ASR model")
    elif passed_checks >= 4:
        print("   🟡 System partially functional")
        print("   🔴 Requires dependency installation")
    else:
        print("   🔴 System not ready")
        print("   🔴 Requires significant setup")

if __name__ == "__main__":
    main()