import os
import sys
import re
from pathlib import Path
import string
from PIL import Image  # images
import subprocess # calling ffmpeg commands

delete_appledouble = True

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".gif", ".ico", ".tga"
}

TEXT_EXTENSIONS = {
    ".html", ".aspx", ".htm", ".css", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".xml", ".yml", ".yaml", ".py", ".java", ".c",
    ".cpp", ".php", ".rb", ".go", ".rs", ".sh", ".bat", ".cmd",
    ".vbs", ".ini", ".md", ".txt", ".vue", ".env", ".java",

    ".unity", ".unitypackage", ".prefab", ".mat", ".meta", ".anim", ".controller", ".meta", ".sln", ".csproj", ".asset", ".cs",

    ".csv", ".tsv", ".log", ".toml", ".cfg", ".spec", ".manifest", ".toc",

    ".mcmeta",

    '.mtl',
    '.gitignore',

    ### EXPERIMENTAL
    ".obj", ".rdp", ".pem", ".config", ".map", ".browser", ".info",
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".alac", ".opus"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".mpeg", ".mpg"
}

"""
checking file signatures for atypical files. goes something like this:
"file extension": [number_of_bytes_to_read, expected_header]

essentially i'm providing a header size then seeing if the file header
does actually contain the expected signature for the given file type.
"""
MISC_SIGNATURES = {

    ".blend":[7,'BLENDER'], ".blend1":[7,'BLENDER'],
    ".fbx": [18, 'Kaydara FBX Binary'],

    ".dll":[2, 'MZ'], ".exe":[2, 'MZ'], ".sys":[2, 'MZ'],
    ".msi":[8, '\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'],

    ".sqlite":[6,'SQLite'],
    ".zip":[4,'PK\x03\x04'],
    ".rar":[7,'\x52\x61\x72\x21\x1A\x07\x00'],
    ".swf": [4, ("CWS", "FWS")],
    ".pyz":[3,'PYZ'],
    ".exr":[4, '\x76\x2F\x31\x01'],

    #adobe
    ".pdf":[4, '%PDF'],
    ".psd":[4, '8BPS'], ".aep": [4, ("JSXJ", "RIFX")],

    # office
    # same signature as .zip as a these are
    # essentially zip files of xml data
    ".docx":[4,'PK\x03\x04'], ".xlsx":[4,'PK\x03\x04'], ".pptx":[4,'PK\x03\x04'], 

    ".doc": [8, '\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'],
    ".xls": [8, '\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'],
    ".ppt": [8, '\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'],

    ".odp":[4,'PK\x03\x04'], ".ods":[4,'PK\x03\x04'], ".odt":[4,'PK\x03\x04'], 

    ".jar":[4,'PK\x03\x04'], 
    ".ttf": [5, '\x00\x01\x00\x00\x00'], ".otf": [4, 'OTTO'],
    ".ess":[4, 'TESV'], ".fos":[11, 'FO3SAVEGAME'], # skyrim save-files lol
    ".resource": [4, 'FSB5'],
    
}

# yes my terminal looks nice
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def get_base_filename(name):
    # files with no name and just an 'extension' behave
    # wierdly. fixing that here:
    if re.match(r"^_\d+\.env$", name):
        return ".env"
    elif re.match(r"^_\d+\.gitignore$", name):
        return ".gitignore"
    
    return re.sub(r"_\d+(?=\.[^\.]+$)", "", name)

def is_image_valid(file_path):
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception as e:
        print(f"  {RED}[!] Invalid image file: {file_path} - {e}{RESET}")
        return False

def is_audio_valid(file_path):
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', str(file_path), '-f', 'null', '-'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"FFmpeg error (code {result.returncode})") 
        elif "Header missing" in result.stderr:
            raise Exception("Header missing") 

        return True
    except Exception as e:
        print(f"{RED}[!] Invalid audio file: {file_path} - {e}{RESET}")
        return False

def is_video_valid(file_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
             str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0 or not result.stdout.strip():
            raise Exception("ffprobe failed or returned no duration.")

        duration = float(result.stdout.strip())
        if duration <= 0.5:
            raise Exception(f"Duration too short: {duration:.3f}s")

        return True
    except Exception as e:
        print(f"{RED}[!] Invalid video file: {file_path} - {e}{RESET}")
        return False
    
def is_misc_valid(file_path, filetype):
    try:
        filetype = filetype.lower()
        read_len, expected = MISC_SIGNATURES[filetype]
        with open(file_path, 'rb') as f:
            head = f.read(read_len)

        ### handle both tuples in case of multiple file signatures
        ### as well as normal string input. flexibility woooooooo
        if isinstance(expected, tuple):
            if not any(head.startswith(sig.encode('utf-8')) for sig in expected):
                raise Exception("Missing starting header (multi), invalid file")
        else:
            if not head.startswith(expected.encode('utf-8')):
                raise Exception("Missing starting header, invalid file")

        return True
    except Exception as e:
        print(e)
        print(f"{RED}[!] Invalid {file_path.suffix} file: {file_path} - {e}{RESET}")
        return False


def analyze_folder(folder_path):
    image_deletions = []
    text_deletions = []
    audio_deletions = []
    video_deletions = []
    misc_file_deletions = []
    renames = []

    print(f"\n{BOLD}{CYAN}🔍 Scanning files and analyzing...{RESET}")

    text_file_groups = {}

    for file in Path(folder_path).rglob("*"):
        if file.is_file():
            # delete macos meta files
            if delete_appledouble and file.name.startswith("._"):
                try:
                    file.unlink()
                    print(f"{RED}🗑️  Deleted AppleDouble metadata file:{RESET} {file}")
                except Exception as e:
                    print(f"{RED}[!] Failed to delete {file}:{RESET} {e}")
                continue

            suffix = file.suffix.lower()

            # IMAGE FILES
            if suffix in IMAGE_EXTENSIONS:
                print(f"  - Checking image: {file.name}")
                if is_image_valid(file):
                    print(f"{GREEN}✅ Valid image file:{RESET} {file.name}")
                    base_name = get_base_filename(file.name)
                    new_name = file.parent / base_name
                    if (file.name != base_name and
                        (not new_name.exists() or new_name in image_deletions or new_name.resolve() == file.resolve())):
                        renames.append((file, new_name))
                else:
                    image_deletions.append(file)

            # TEXT FILES (group and process later)
            elif suffix in TEXT_EXTENSIONS or file.name.lower() in TEXT_EXTENSIONS: 
                # .env // .gitignore files have no suffix
                base_name = get_base_filename(file.name)
                key = (file.parent, base_name)
                text_file_groups.setdefault(key, []).append(file)

            # AUDIO FILES        
            elif suffix in AUDIO_EXTENSIONS:
                print(f"  - Checking audio file: {file.name}")
                if is_audio_valid(file):
                    print(f"{GREEN}✅ Valid audio file:{RESET} {file.name}")
                    base_name = get_base_filename(file.name)
                    new_name = file.parent / base_name
                    if (file.name != base_name and
                        (not new_name.exists() or new_name in audio_deletions or new_name.resolve() == file.resolve())):
                        renames.append((file, new_name))
                else:
                    audio_deletions.append(file)

            elif suffix in VIDEO_EXTENSIONS:
                print(f"  - Checking video file: {file.name}")
                if is_video_valid(file):
                    print(f"{GREEN}✅ Valid video file:{RESET} {file.name}")
                    base_name = get_base_filename(file.name)
                    new_name = file.parent / base_name
                    if (file.name != base_name and
                        (not new_name.exists() or new_name in video_deletions or new_name.resolve() == file.resolve())):
                        renames.append((file, new_name))
                else:
                    video_deletions.append(file)

            elif suffix in MISC_SIGNATURES:
                print(f"  - Checking {file.suffix} file: {file.name}")
                if is_misc_valid(file, file.suffix):
                    print(f"{GREEN}✅ Valid {file.suffix} file:{RESET} {file.name}")
                    base_name = get_base_filename(file.name)
                    new_name = file.parent / base_name
                    if (file.name != base_name and
                        (not new_name.exists() or new_name in misc_file_deletions or new_name.resolve() == file.resolve())):
                        renames.append((file, new_name))
                else:
                    misc_file_deletions.append(file)

    # now handle grouped text files
    for (parent, base_name), variants in text_file_groups.items():
        print(f"\n{CYAN}📄 Group: {base_name}{RESET}")
        best_candidates = []
        best_ratio = 1.0

        for file in variants:
            try:
                size = file.stat().st_size
                with open(file, 'rb') as f:
                    head = f.read(2048)
                non_printable = sum(1 for b in head if chr(b) not in string.printable)
                ratio = non_printable / len(head) if head else 1
            except Exception as e:
                size = 0
                ratio = 1
                print(f"  {RED}[!] Could not read {file.name}: {e}{RESET}")

            print(f"  - {file.name} | size: {size} bytes | non-printable ratio: {ratio:.3f}")

            if size > 0 and ratio < best_ratio:
                best_candidates = [file] 
                best_ratio = ratio
                """
                this next part is only true if the program has already encountered a
                working file, meaning the working best ratio has been set to 0.000...
                finding a file that is equal to this means that there is another
                working file, and we cannot delete that so we save it too.
                """
            elif f"{ratio:.3f}" == f"{best_ratio:.3f}":
                best_candidates.append(file)
            
        if len(best_candidates) == 1: # only one file, proceed as normal
            print(f"  {GREEN}=> Keeping: {best_candidates[0].name}{RESET}")
            base_name_file = parent / base_name
            if (best_candidates[0].name != base_name and
                (not base_name_file.exists() or base_name_file in text_deletions or base_name_file.resolve() != best_candidates[0].resolve())):
                renames.append((best_candidates[0], base_name_file))

            for file in variants:
                if file != best_candidates[0]:
                    print(f"  {RED}=> Deleting: {file.name}{RESET}")
                    text_deletions.append(file)

        elif len(best_candidates) > 1:  
            # Pick the one closest to base_name as the "main" file
            chosen = None
            for candidate in best_candidates:
                if candidate.name == base_name:
                    chosen = candidate
                    break
            if not chosen:
                # fallback to first best candidate
                chosen = best_candidates[0]
            
            print(f"  {GREEN}=> Keeping (primary): {chosen.name}{RESET}")
            base_name_file = parent / base_name
            if (chosen.name != base_name and
                (not base_name_file.exists() or base_name_file in text_deletions or base_name_file.resolve() != chosen.resolve())):
                renames.append((chosen, base_name_file))

            # Keep all best candidates, remove the rest
            for candidate in best_candidates:
                if candidate != chosen:
                    print(f"  {GREEN}=> Keeping (also valid): {candidate.name}{RESET}")

            for file in variants:
                if file not in best_candidates:
                    print(f"  {RED}=> Deleting: {file.name}{RESET}")
                    text_deletions.append(file)

        else:
            print(f"  {YELLOW}=> No valid text file found in group. Deleting all.{RESET}")
            text_deletions.extend(variants)

    print(f"\n{'='*60}")
    print(f"{YELLOW}🗑️  Image files marked for deletion (broken images):{RESET} {len(image_deletions)}")
    print(f"{YELLOW}🗑️  Text files marked for deletion (broken text):{RESET} {len(text_deletions)}")
    print(f"{YELLOW}🗑️  Audio files marked for deletion (broken audio):{RESET} {len(audio_deletions)}")
    print(f"{YELLOW}🗑️  Video files marked for deletion (broken video):{RESET} {len(video_deletions)}")
    print(f"{YELLOW}🗑️  Misc. files marked for deletion (broken data):{RESET} {len(misc_file_deletions)}")
    print(f"{YELLOW}✏️  Files to rename:{RESET} {len(renames)}")
    
    confirm = input(f"{BOLD}⚠️  Proceed with deletion and renaming? (Y/N): {RESET}").strip().lower()

    if confirm.lower() == 'y':
        for file in image_deletions + text_deletions + audio_deletions + video_deletions + misc_file_deletions:
            try:
                file.unlink()
                print(f"{RED}🗑️  Deleted:{RESET} {file}")
            except Exception as e:
                print(f"{RED}[!] Failed to delete {file}:{RESET} {e}")

        for src, dst in renames:
            try:
                src.rename(dst)
                print(f"{GREEN}✏️  Renamed:{RESET} {src.name} → {dst.name}")
            except Exception as e:
                print(f"{RED}[!] Failed to rename {src.name}:{RESET} {e}")
    else:
        print(f"{YELLOW}⚠️  Aborted. No files were changed.{RESET}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"{RED}Usage: python ByteSweep.py \"Path/To/Folder\"{RESET}")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"{RED}Invalid folder: {folder}{RESET}")
        sys.exit(1)

    print(f"{CYAN}📂 Analyzing folder:{RESET} {folder}")
    analyze_folder(folder)
    print(f"\n{GREEN}🎉 Done.{RESET}")
