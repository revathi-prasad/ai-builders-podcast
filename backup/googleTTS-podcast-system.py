import os
import json
import time
import random
import requests
from google.cloud import texttospeech
import anthropic
from pydub import AudioSegment, effects
import argparse

# Configuration
class Config:
    # Anthropic Claude settings
    CLAUDE_API_KEY = "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"  # Replace with your API key
    MODEL = "claude-3-7-sonnet-20250219"  # Options: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
    
    # Google Text-to-Speech settings
    SPEAKER_VOICES = {
        "Sascha": "en-US-Neural2-J",  # Advanced male voice
        "Marina": "en-US-Neural2-F"   # Advanced female voice
    }
    
    # Conversation settings
    MAX_TURNS = 15  # Maximum conversation turns
    TEMPERATURE = 0.7  # Creativity level (higher = more creative)
    SCRIPT_ADHERENCE = 0.7  # How closely to follow script (0-1)
    
    # Audio settings
    PAUSE_BETWEEN_TURNS = 500  # milliseconds

# Initialize the Claude client
claude_client = anthropic.Anthropic(api_key=Config.CLAUDE_API_KEY)

# Initialize Google TTS client
tts_client = texttospeech.TextToSpeechClient()

def add_dynamic_expression(text, speaker):
    """Add dynamic expression with consistent volume levels"""
    
    # Split text into sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Start building SSML
    ssml = "<speak>\n"
    
    # Set base voice characteristics by speaker
    if speaker == "Sascha":
        # Sascha - slightly deeper, confident tone
        base_rate = "96%"
        base_pitch = "-1st"
        question_pitch = "+0st"
        exclamation_pitch = "+1st"
        emphasis_pitch = "+0st"  # Moderate emphasis
        emphasis_rate = "93%"    # Slightly slower for emphasis
    else:  # Marina
        # Marina - slightly higher, more animated tone
        base_rate = "98%"
        base_pitch = "+0st"
        question_pitch = "+2st"
        exclamation_pitch = "+3st"
        emphasis_pitch = "+1st"  # Higher emphasis
        emphasis_rate = "95%"    # Slightly slower for emphasis
    
    # Words to emphasize with their patterns - NO volume changes
    emphasis_patterns = {
        r'\b(really|very|absolutely|definitely|extremely)\b': 'strong',
        r'\b(important|critical|essential|crucial|vital)\b': 'strong',
        r'\b(never|always|must|need to|have to)\b': 'moderate',
        r'\b(amazing|incredible|fantastic|awesome|wonderful)\b': 'strong',
        r'\b(terrible|horrible|awful|disastrous)\b': 'strong',
        r'\b(first|second|third|finally|lastly)\b': 'moderate',
        r'\b(but|however|although|nevertheless|yet)\b': 'moderate',
        r'\b(for example|specifically|particularly|especially)\b': 'moderate'
    }
    
    # Filler word replacements with consistent volume
    filler_replacements = {
        r'\bum\b': '<break time="200ms"/><prosody rate="80%" pitch="-2st">uhm</prosody><break time="100ms"/>',
        r'\buh\b': '<break time="200ms"/><prosody rate="80%" pitch="-2st">uh</prosody><break time="100ms"/>',
        r'\blike\b(?!\s+to|\s+the|\s+a|\s+an|\s+\w+ing)': '<prosody rate="90%">like</prosody>',  # Only conversational "like"
        r'\byou know\b': '<prosody rate="110%">you know</prosody>',
        r'\bI mean\b': '<prosody rate="105%">I mean</prosody>',
        r'\bactually\b': '<prosody rate="95%">actually</prosody>',
        r'\bbasically\b': '<prosody rate="95%">basically</prosody>',
        r'\bkind of\b': '<prosody rate="90%">kind of</prosody>',
        r'\bsort of\b': '<prosody rate="90%">sort of</prosody>',
        r', right\b': ', <prosody pitch="+2st">right</prosody>',
        r', yeah\b': ', <prosody pitch="+1st">yeah</prosody>'
    }
    
    for sentence in sentences:
        # Make a working copy of the sentence
        modified_sentence = sentence
        
        # Apply filler word replacements
        for pattern, replacement in filler_replacements.items():
            modified_sentence = re.sub(pattern, replacement, modified_sentence, flags=re.IGNORECASE)
        
        # Apply emphasis to specific words - WITHOUT volume changes
        for pattern, level in emphasis_patterns.items():
            # Use a function to handle the replacement
            def emphasis_replacer(match):
                word = match.group(0)
                if level == 'strong':
                    return f'<prosody rate="{emphasis_rate}" pitch="{emphasis_pitch}"><emphasis level="strong">{word}</emphasis></prosody>'
                else:
                    return f'<prosody rate="{emphasis_rate}" pitch="{emphasis_pitch}"><emphasis level="moderate">{word}</emphasis></prosody>'
            
            modified_sentence = re.sub(pattern, emphasis_replacer, modified_sentence, flags=re.IGNORECASE)
        
        # Handle repeated words - NO volume changes
        modified_sentence = re.sub(r'\b(\w+)(\s+\1\b)+', r'<prosody rate="90%" pitch="-1st">\1</prosody> <prosody rate="95%" pitch="+1st">\1</prosody>', modified_sentence)
        
        # Process sentence based on type (but consistent volume)
        if modified_sentence.strip().endswith('?'):
            # Questions - rising intonation
            if not re.search(r'<emphasis', modified_sentence):
                modified_sentence = re.sub(r'\b(what|how|why|where|when|who)\b', 
                                         r'<emphasis level="moderate">\1</emphasis>', 
                                         modified_sentence, flags=re.IGNORECASE)
            ssml += f'<prosody rate="{base_rate}" pitch="{question_pitch}">{modified_sentence} <break time="300ms"/></prosody>\n'
        
        elif modified_sentence.strip().endswith('!'):
            # Exclamations - NO volume change
            ssml += f'<prosody rate="102%" pitch="{exclamation_pitch}">{modified_sentence} <break time="300ms"/></prosody>\n'
        
        else:
            # Normal statements
            ssml += f'<prosody rate="{base_rate}" pitch="{base_pitch}">{modified_sentence} <break time="250ms"/></prosody>\n'
    
    ssml += "</speak>"
    return ssml

def text_to_speech(text, speaker_name):
    """Convert text to speech using Google TTS with consistent volume"""
    
    # Create output directory if it doesn't exist
    os.makedirs("audio-files", exist_ok=True)
    
    # Process the text with dynamic expression but consistent volume
    processed_text = add_dynamic_expression(text, speaker_name)
    
    # Prepare the synthesis input with enhanced SSML
    synthesis_input = texttospeech.SynthesisInput(ssml=processed_text)
    
    # Set the voice parameters
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name=Config.SPEAKER_VOICES[speaker_name]
    )
    
    # Select the audio file type with consistent audio level
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,  # Base speaking rate (can be modified in SSML for specific parts)
        pitch=0.0,          # Base pitch (can be modified in SSML for specific parts)
        volume_gain_db=0.0  # Consistent volume level
    )
    
    # Generate the speech
    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        # Generate a unique filename
        timestamp = int(time.time())
        filename = f"audio-files/{timestamp}_{speaker_name}.mp3"
        
        # Write the response to the output file
        with open(filename, "wb") as out:
            out.write(response.audio_content)
            
        print(f'Audio content written to file "{filename}"')
        return filename
        
    except Exception as e:
        print(f"Error synthesizing speech: {e}")
        return None

def merge_audio_files(filenames, output_file="podcast.mp3"):
    """Merge audio files with volume normalization"""
    
    if not filenames:
        print("No audio files to merge")
        return
    
    # Start with the first file
    combined = AudioSegment.from_mp3(filenames[0])
    
    # Apply normalization to first segment
    combined = effects.normalize(combined)
    
    # Add a pause between turns
    pause = AudioSegment.silent(duration=Config.PAUSE_BETWEEN_TURNS)
    
    # Add each subsequent file with a pause
    for file in filenames[1:]:
        # Load and normalize this segment
        segment = AudioSegment.from_mp3(file)
        segment = effects.normalize(segment)
        
        # Add to combined audio
        combined += pause
        combined += segment
    
    # Final normalization pass to ensure consistency
    combined = effects.normalize(combined)
    
    # Export the combined audio
    combined.export(output_file, format="mp3")
    print(f"Created podcast with consistent volume at {output_file}")

class PodcastAgent:
    def __init__(self, name, persona, voice):
        self.name = name
        self.persona = persona
        self.voice = voice
        self.context = []
    
    def generate_response(self, script_point, conversation_history, opponent_last_message):
        """Generate a response based on the script point and conversation history"""
        
        # Construct prompt with personality, history, and script guidance
        system_prompt = f"""You are {self.name}, a podcast host with the following persona: {self.persona}
        
You're having a conversation with your co-host. Your responses should:
1. Stay generally on topic with the script points
2. Feel natural and conversational (use filler words occasionally)
3. Include your own thoughts and insights
4. Reference what your co-host just said
5. Keep responses between 2-4 sentences (30-100 words)
6. Never explicitly mention that you're following a script

Use a natural speaking style with occasional "um", "uh", "like", or similar filler words to sound more human. Use these sparingly to sound natural, not forced."""

        # Format conversation history for Claude
        conversation_text = ""
        for entry in conversation_history[-6:]:  # Only use last 6 entries to conserve context
            speaker_name = entry["speaker"]
            message = entry["text"]
            conversation_text += f"{speaker_name}: {message}\n\n"
        
        # Prepare script guidance message
        script_guidance = f"""The current topic you should discuss is: {script_point}
        
You should generally follow this topic, but you can add your own thoughts and perspectives. Your co-host just said: '{opponent_last_message}'

Respond naturally to what they said while keeping the conversation moving forward. Make your response sound natural in spoken form.

Include occasional filler words like "um", "uh", "you know", or "I mean" where they would naturally occur in conversation, but use them sparingly."""

        # Construct the final prompt for Claude
        prompt = f"""
Here's the previous conversation:

{conversation_text}

{script_guidance}

Remember to stay in character as {self.name} and speak conversationally. What do you say next?
"""

        # Make API call to generate response
        try:
            message = claude_client.messages.create(
                model=Config.MODEL,
                max_tokens=150,
                temperature=Config.TEMPERATURE,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Well, that's an interesting point. Let me think about that for a moment..."

def extract_script_points(script_file):
    """Extract scripted conversation points from a script file"""
    script_points = []
    
    # Determine script format based on file extension
    if script_file.endswith('.json'):
        # Parse JSON script
        with open(script_file, 'r') as f:
            script_data = json.load(f)
            
        for item in script_data:
            script_points.append({
                "speaker": item["speaker"],
                "text": item["text"]
            })
            
    else:
        # Parse text script format (Sascha: line, Marina: line)
        with open(script_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                if ":" in line:
                    parts = line.split(":", 1)
                    speaker = parts[0].strip()
                    text = parts[1].strip()
                    script_points.append({
                        "speaker": speaker,
                        "text": text
                    })
    
    return script_points

def run_semi_scripted_conversation(script_file, output_file="podcast.mp3", use_script=0.7):
    """Run a semi-scripted conversation between two podcast agents"""
    
    # Define agent personas
    sascha_persona = """You are Sascha, an enthusiastic and knowledgeable tech podcast host. 
    You're passionate about AI, machine learning, and how technology impacts society.
    Your communication style is energetic, insightful, and occasionally you use technical terminology
    but explain it clearly. You ask thoughtful follow-up questions to your co-host."""
    
    marina_persona = """You are Marina, a thoughtful and articulate podcast co-host.
    You have a background in both technology and humanities, giving you a unique perspective.
    Your communication style is warm, inquisitive, and you often bring conversations back to 
    the human impact of technology. You're good at making complex topics accessible."""
    
    # Create the podcast agents
    sascha = PodcastAgent("Sascha", sascha_persona, Config.SPEAKER_VOICES["Sascha"])
    marina = PodcastAgent("Marina", marina_persona, Config.SPEAKER_VOICES["Marina"])
    
    # Extract script points from file
    script_points = extract_script_points(script_file)
    
    # Initialize conversation tracking
    conversation_history = []
    audio_files = []
    
    # Determine who speaks first based on script
    current_speaker = script_points[0]["speaker"] if script_points else "Sascha"
    
    # Run the conversation for a set number of turns
    for turn in range(Config.MAX_TURNS):
        print(f"Turn {turn+1}: {current_speaker} speaking...")
        
        # Get the relevant agent
        agent = sascha if current_speaker == "Sascha" else marina
        opponent = marina if current_speaker == "Sascha" else sascha
        
        # Determine if this turn should follow script or improvise
        use_script_for_turn = turn < len(script_points) and script_points[turn]["speaker"] == current_speaker
        
        if use_script_for_turn and random.random() < use_script:
            # Use the scripted text
            response = script_points[turn]["text"]
            print(f"[SCRIPT] {current_speaker}: {response}")
        else:
            # Get script guidance (if available)
            script_guidance = ""
            for script_point in script_points:
                if script_point["speaker"] == current_speaker:
                    script_guidance = script_point["text"]
                    break
            
            # Get the last message from opponent
            opponent_last_message = ""
            for entry in reversed(conversation_history):
                if entry["speaker"] == opponent.name:
                    opponent_last_message = entry["text"]
                    break
            
            # Generate a response
            response = agent.generate_response(script_guidance, conversation_history, opponent_last_message)
            print(f"[AI] {current_speaker}: {response}")
        
        # Add to conversation history
        conversation_history.append({
            "speaker": current_speaker,
            "text": response
        })
        
        # Convert to speech
        audio_file = text_to_speech(response, current_speaker)
        if audio_file:
            audio_files.append(audio_file)
        
        # Switch speakers
        current_speaker = "Marina" if current_speaker == "Sascha" else "Sascha"
        
        # Small delay to avoid rate limits
        time.sleep(1)
    
    # Merge all audio files into a single podcast
    merge_audio_files(audio_files, output_file)
    
    # Save conversation transcript
    with open("transcript.json", "w") as f:
        json.dump(conversation_history, f, indent=2)
    
    return conversation_history

def main():
    parser = argparse.ArgumentParser(description="Generate a semi-scripted AI podcast")
    parser.add_argument("--script", required=True, help="Path to script file (JSON or TXT)")
    parser.add_argument("--output", default="podcast.mp3", help="Output podcast filename")
    parser.add_argument("--adherence", type=float, default=0.7, 
                      help="Script adherence level (0-1, where 1 means strictly follow script)")
    
    args = parser.parse_args()
    
    # Run the conversation
    conversation = run_semi_scripted_conversation(
        args.script, 
        args.output,
        args.adherence
    )
    
    print(f"Podcast generated successfully: {args.output}")
    print(f"Transcript saved to: transcript.json")

if __name__ == "__main__":
    main()