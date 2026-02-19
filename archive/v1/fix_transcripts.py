"""
Fix podcast transcript inconsistencies
"""

import argparse
import logging
import re
import sys
from typing import List, Dict, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('transcript_fix.log')
    ]
)

def fix_transcript(input_file: str, output_file: str, language: str) -> None:
    """Fix inconsistencies in a podcast transcript
    
    Args:
        input_file: Path to input transcript file
        output_file: Path to output transcript file
        language: Language of the transcript (hindi, tamil)
    """
    # Define mappings
    mappings = {
        "hindi": {
            "speakers": {"ALEX": "ARJUN", "MAYA": "PRIYA"},
            "podcast_title": {
                "Future Proof with AI": "नई तकनीक, नए अवसर",
                "फ्यूचर प्रूफ विद AI": "नई तकनीक, नए अवसर"
            }
        },
        "tamil": {
            "speakers": {"ALEX": "KARTHIK", "MAYA": "MEERA"},
            "podcast_title": {
                "Future Proof with AI": "புதிய மனிதருடன் ஆழ்நோக்கம்",
                "ஃப்யூச்சர் ப்ரூஃப் வித் AI": "புதிய மனிதருடன் ஆழ்நோக்கம்"
            }
        }
    }
    
    if language not in mappings:
        logging.error(f"Unsupported language: {language}")
        return
    
    try:
        # Read the transcript
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Apply speaker mapping
        for source, target in mappings[language]["speakers"].items():
            # Replace speaker labels at the start of lines
            content = re.sub(f"^{source}:", f"{target}:", content, flags=re.MULTILINE)
        
        # Apply podcast title mapping
        for source, target in mappings[language]["podcast_title"].items():
            content = content.replace(source, target)
        
        # Remove duplicate outro sections
        # Find standard outro for the language
        standard_outros = {
            "hindi": "ARJUN: नई तकनीक, नए अवसर के इस एपिसोड के लिए बस इतना ही।",
            "tamil": "KARTHIK: புதிய மனிதருடன் ஆழ்நோக்கம் நிகழ்ச்சியின் இந்த அத்தியாயத்திற்கு அவ்வளவுதான்।"
        }
        
        # Check if we have both English and target language outros
        if "ALEX: That's all for this episode" in content and standard_outros[language] in content:
            # Remove the English outro and everything after it, up to the target language outro
            english_outro_start = content.find("ALEX: That's all for this episode")
            target_outro_start = content.find(standard_outros[language])
            
            if english_outro_start > 0 and target_outro_start > 0:
                content = content[:english_outro_start] + content[target_outro_start:]
        
        # Write the fixed transcript
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        logging.info(f"Fixed transcript saved to: {output_file}")
        
    except Exception as e:
        logging.error(f"Error fixing transcript: {e}")

def main():
    parser = argparse.ArgumentParser(description="Fix podcast transcript inconsistencies")
    
    parser.add_argument("--input", required=True, help="Path to input transcript file")
    parser.add_argument("--output", required=True, help="Path to output transcript file")
    parser.add_argument("--language", required=True, choices=["hindi", "tamil"],
                      help="Language of the transcript")
    
    args = parser.parse_args()
    
    fix_transcript(args.input, args.output, args.language)

if __name__ == "__main__":
    main()