# Save this file as modal_app.py
import modal
import os
import subprocess
import uuid
from flask import Flask, request, send_file

# Define the Modal app and the container image
stub = modal.App("video-processor-app")
image = modal.Image.debian_slim().apt_install("wget", "ffmpeg").pip_install("flask")

@stub.function(image=image)
@stub.wsgi_app()
def flask_app():
    # Initialize the Flask application
    app = Flask(__name__)

    @app.route('/loop-and-concat', methods=['POST'])
    def loop_and_concat():
        # Get the JSON data from the request
        data = request.json
        video_url = data.get('video_url')
        audio1_url = data.get('audio1_url')
        audio2_url = data.get('audio2_url')

        # Check if all required URLs are provided
        if not all([video_url, audio1_url, audio2_url]):
            return "Error: Missing one or more URLs.", 400

        # Generate unique filenames in the temporary directory
        unique_id = str(uuid.uuid4())
        video_in = f"/tmp/{unique_id}_video"
        audio1_in = f"/tmp/{unique_id}_audio1"
        audio2_in = f"/tmp/{unique_id}_audio2"
        output_file = f"/tmp/{unique_id}_output.mp4"

        try:
            # Download all three files using wget
            print("Downloading files...")
            subprocess.run(['wget', video_url, '-O', video_in], check=True)
            subprocess.run(['wget', audio1_url, '-O', audio1_in], check=True)
            subprocess.run(['wget', audio2_url, '-O', audio2_in], check=True)
            print("Downloads complete.")

            # Construct and execute the FFmpeg command
            command = [
                'ffmpeg', '-y', '-stream_loop', '-1', '-i', video_in,
                '-i', audio1_in, '-i', audio2_in,
                '-filter_complex', '[1:a][2:a]concat=n=2:v=0:a=1[outa]',
                '-map', '0:v', '-map', '[outa]',
                '-c:v', 'libx264', '-c:a', 'aac', '-shortest', output_file
            ]
            print("Running FFmpeg...")
            subprocess.run(command, check=True, capture_output=True, text=True)
            print("FFmpeg processing finished.")

            # Send the final processed file back as a download
            return send_file(output_file, as_attachment=True)

        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Error: {e.stderr}")
            return f"FFmpeg Error: {e.stderr}", 500
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return str(e), 500
        finally:
            # Clean up temporary files
            print("Cleaning up temporary files...")
            for f in [video_in, audio1_in, audio2_in, output_file]:
                if os.path.exists(f):
                    os.remove(f)
            print("Cleanup complete.")

    return app
