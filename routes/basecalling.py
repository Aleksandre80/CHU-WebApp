from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file
from extensions import db
from models import ConfigurationBasecalling, Workflow
from utils import role_requis
import json

basecalling_bp = Blueprint('basecalling_bp', __name__)

configurations_basecalling = []

@basecalling_bp.route('/basecalling', methods=['GET', 'POST'])
@role_requis('superadmin') 
def basecalling():
    if request.method == 'POST':
        base_output_dir = request.form['base_output_dir']
        input_dir = request.form['input_dir']
        ref_genome_path = request.form['ref_genome']
        qs_scores = request.form['qs_scores']
        cuda_device = request.form['cuda_device']
        model = request.form['model']
        kit_name = request.form['kit_name']

        if not all([base_output_dir, input_dir, ref_genome_path, qs_scores, cuda_device, model, kit_name]):
            flash('Please fill all fields before adding a configuration.', 'error')
            return redirect(url_for('basecalling_bp.basecalling'))
        
        configurations_basecalling.append({
            "base_output_dir": base_output_dir,
            "input_dir": input_dir,
            "ref_genome": ref_genome_path,
            "qs_scores": qs_scores,
            "cuda_device": cuda_device,
            "model": model,
            "kit_name": kit_name
        })
        
        configurations_basecalling_db = ConfigurationBasecalling(
            base_output_dir=base_output_dir,
            input_dir=input_dir,
            ref_genome=ref_genome_path,
            qs_scores=qs_scores,
            cuda_device=cuda_device,
            model=model,
            kit_name=kit_name
        )
        db.session.add(configurations_basecalling_db)
        db.session.commit()
        
        flash('Configuration added successfully.', 'success')
        return jsonify({'success': True, 'configurations': configurations_basecalling}), 200

    return render_template('index.html', configurations=configurations_basecalling)

@basecalling_bp.route('/generate_script', methods=['GET'])
@role_requis('superadmin') 
def generate_script():
    script_content = "#!/bin/bash\n\nsource /home/grid/miniconda3/etc/profile.d/conda.sh\nconda activate genomics\n\n"
    for config in configurations_basecalling:
        log_file = f"{config['base_output_dir']}/basecalling_log.txt"
        report_file = f"{config['base_output_dir']}/basecalling_report.html"
        
        script_content += f"echo \"$(date '+%Y-%m-%d %H:%M:%S') - Starting basecalling for input directory {config['input_dir']}\" >> \"{log_file}\"\n"
        
        qs_scores_list = config['qs_scores'].split()
        for qscore in qs_scores_list:
            output_dir = f"${{BASE_OUTPUT_DIR}}/demultiplexed_q{qscore}"
            script_content += f"BASE_OUTPUT_DIR=\"{config['base_output_dir']}\"\n"
            script_content += "mkdir -p \"${BASE_OUTPUT_DIR}\"\n"
            script_content += f"""
DORADO_BIN="/home/grid/dorado-0.7.2-linux-x64/bin/dorado"
MODEL_PATH="/home/grid/dorado-0.7.2-linux-x64/bin/{config['model']}"
REF_GENOME="{config['ref_genome']}"
INPUT_DIR="{config['input_dir']}"
OUTPUT_DIR="{output_dir}"
mkdir -p "${{OUTPUT_DIR}}"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting basecalling and demultiplexing for Q-score {qscore}" >> \"{log_file}\"
${{DORADO_BIN}} basecaller -x "{config['cuda_device']}" --min-qscore "{qscore}" --no-trim --emit-fastq ${{MODEL_PATH}} ${{INPUT_DIR}} | \\
${{DORADO_BIN}} demux --kit-name "{config['kit_name']}" --emit-fastq --output-dir "${{OUTPUT_DIR}}"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Processing complete for {config['input_dir']} with Q-score {qscore}" >> \"{log_file}\"
"""
            script_content += f"for fastq_file in \"${{OUTPUT_DIR}}\"/*.fastq; do\n"
            script_content += f"    bam_file=\"${{fastq_file%.fastq}}.bam\"\n"
            script_content += f"    echo \"$(date '+%Y-%m-%d %H:%M:%S') - Aligning ${{fastq_file}} to reference genome...\" >> \"{log_file}\"\n"
            script_content += f"    minimap2 -ax map-ont \"{config['ref_genome']}\" \"$fastq_file\" | samtools sort -o \"$bam_file\"\n"
            script_content += f"    samtools index \"$bam_file\"\n"
            script_content += f"    echo \"$(date '+%Y-%m-%d %H:%M:%S') - Alignment and BAM conversion completed for ${{bam_file}}\" >> \"{log_file}\"\n"
            script_content += "done\n"
    
    script_content += f"echo \"$(date '+%Y-%m-%d %H:%M:%S') - All processes are complete.\" >> \"{log_file}\"\n"
    
    # Generate HTML report
    script_content += f"echo '<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Basecalling Log Report</title></head><body><div class=\"log-container\"><h1>Basecalling Log Report</h1>' > \"{report_file}\"\n"
    script_content += f"while IFS= read -r line; do\n"
    script_content += f"    echo \"<div class='log-entry'>\"$line\"</div>\" >> \"{report_file}\"\n"
    script_content += f"done < \"{log_file}\"\n"
    script_content += f"echo '</div></body></html>' >> \"{report_file}\"\n"
    
    # Échapper les caractères spéciaux pour JSON
    escaped_script_content = json.dumps(script_content)

    return jsonify(script=escaped_script_content)


@basecalling_bp.route('/download_basecalling_script', methods=['GET'])
@role_requis('superadmin')
def download_basecalling_script():
    script_content = "#!/bin/bash\n\nsource /home/grid/miniconda3/etc/profile.d/conda.sh\nconda activate genomics\n\n"
    for config in configurations_basecalling:
        log_file = f"{config['base_output_dir']}/basecalling_log.txt"
        report_file = f"{config['base_output_dir']}/basecalling_report.html"
        
        script_content += f"echo \"$(date '+%Y-%m-%d %H:%M:%S') - Starting basecalling for input directory {config['input_dir']}\" >> \"{log_file}\"\n"
        
        qs_scores_list = config['qs_scores'].split()
        for qscore in qs_scores_list:
            output_dir = f"${{BASE_OUTPUT_DIR}}/demultiplexed_q{qscore}"
            script_content += f"BASE_OUTPUT_DIR=\"{config['base_output_dir']}\"\n"
            script_content += "mkdir -p \"${BASE_OUTPUT_DIR}\"\n"
            script_content += f"""
DORADO_BIN="/home/grid/dorado-0.7.2-linux-x64/bin/dorado"
MODEL_PATH="/home/grid/dorado-0.7.2-linux-x64/bin/{config['model']}"
REF_GENOME="{config['ref_genome']}"
INPUT_DIR="{config['input_dir']}"
OUTPUT_DIR="{output_dir}"
mkdir -p "${{OUTPUT_DIR}}"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting basecalling and demultiplexing for Q-score {qscore}" >> \"{log_file}\"
${{DORADO_BIN}} basecaller -x "{config['cuda_device']}" --min-qscore "{qscore}" --no-trim --emit-fastq ${{MODEL_PATH}} ${{INPUT_DIR}} | \\
${{DORADO_BIN}} demux --kit-name "{config['kit_name']}" --emit-fastq --output-dir "${{OUTPUT_DIR}}"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Processing complete for {config['input_dir']} with Q-score {qscore}" >> \"{log_file}\"
"""
            script_content += f"for fastq_file in \"${{OUTPUT_DIR}}\"/*.fastq; do\n"
            script_content += f"    bam_file=\"${{fastq_file%.fastq}}.bam\"\n"
            script_content += f"    echo \"$(date '+%Y-%m-%d %H:%M:%S') - Aligning ${{fastq_file}} to reference genome...\" >> \"{log_file}\"\n"
            script_content += f"    minimap2 -ax map-ont \"{config['ref_genome']}\" \"$fastq_file\" | samtools sort -o \"$bam_file\"\n"
            script_content += f"    samtools index \"$bam_file\"\n"
            script_content += f"    echo \"$(date '+%Y-%m-%d %H:%M:%S') - Alignment and BAM conversion completed for ${{bam_file}}\" >> \"{log_file}\"\n"
            script_content += "done\n"
    
    script_content += f"echo \"$(date '+%Y-%m-%d %H:%M:%S') - All processes are complete.\" >> \"{log_file}\"\n"
    
    # Generate HTML report
    script_content += f"echo '<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Basecalling Log Report</title></head><body><div class=\"log-container\"><h1>Basecalling Log Report</h1>' > \"{report_file}\"\n"
    script_content += f"while IFS= read -r line; do\n"
    script_content += f"    echo \"<div class='log-entry'>\"$line\"</div>\" >> \"{report_file}\"\n"
    script_content += f"done < \"{log_file}\"\n"
    script_content += f"echo '</div></body></html>' >> \"{report_file}\"\n"
    
    script_path = '/data/Script_Site/tmp/basecalling_script.sh'
    with open(script_path, 'w') as file:
        file.write(script_content)
    
    response = make_response(send_file(script_path, as_attachment=True, download_name="basecalling_script.sh"))
    response.headers["Content-Disposition"] = "attachment; filename=basecalling_script.sh"
    return response

@basecalling_bp.route('/get_configurations_basecalling', methods=['GET'])
@role_requis('superadmin')
def get_configurations_basecalling():
    return jsonify(configurations_basecalling)

@basecalling_bp.route('/delete_config_basecalling', methods=['POST'])
@role_requis('superadmin')
def delete_configuration_basecalling():
    index = request.json['index']
    try:
        configurations_basecalling.pop(index)
        return jsonify(success=True, message="Configuration deleted successfully.")
    except IndexError:
        return jsonify(success=False, message="Configuration not found.")
