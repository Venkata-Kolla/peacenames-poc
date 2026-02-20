"""
============================================================================
PEACENAMES POC - BACKEND API
============================================================================
"""

import os
import json
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import pooling

# ============================================================================
# APP CONFIGURATION
# ============================================================================

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Railway provides MYSQL* variables - read them with fallbacks for local dev
db_host = os.environ.get('MYSQLHOST', os.environ.get('DB_HOST', 'localhost'))
db_port = int(os.environ.get('MYSQLPORT', os.environ.get('DB_PORT', 3306)))
db_user = os.environ.get('MYSQLUSER', os.environ.get('DB_USER', 'root'))
db_password = os.environ.get('MYSQLPASSWORD', os.environ.get('DB_PASSWORD', 'peacenames'))
db_name = os.environ.get('MYSQLDATABASE', os.environ.get('DB_NAME', 'peacenames'))

app.config.update(
    DB_HOST=db_host,
    DB_PORT=db_port,
    DB_USER=db_user,
    DB_PASSWORD=db_password,
    DB_NAME=db_name,
    UPLOAD_FOLDER=os.environ.get('UPLOAD_FOLDER', './uploads'),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 
                        'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'mp4', 'mp3'}
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db_config = {
    'host': app.config['DB_HOST'],
    'port': app.config['DB_PORT'],
    'user': app.config['DB_USER'],
    'password': app.config['DB_PASSWORD'],
    'database': app.config['DB_NAME'],
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

connection_pool = None

def get_db_pool():
    global connection_pool
    if connection_pool is None:
        try:
            connection_pool = pooling.MySQLConnectionPool(
                pool_name="peacenames_pool",
                pool_size=5,
                pool_reset_session=True,
                **db_config
            )
            app.logger.info("Database connection pool created successfully")
        except Exception as e:
            app.logger.error(f"Failed to create connection pool: {e}")
            raise
    return connection_pool

def get_db_connection():
    return get_db_pool().get_connection()

def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if commit:
            conn.commit()
            return cursor.lastrowid
        elif fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        
    except mysql.connector.Error as e:
        app.logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/dimensions', methods=['GET'])
def get_dimensions():
    try:
        query = """
            SELECT id, code, name_en, name_zh, display_order, icon_name
            FROM dimensions
            ORDER BY display_order
        """
        dimensions = execute_query(query)
        return jsonify({'success': True, 'data': dimensions})
    except Exception as e:
        app.logger.error(f"Error fetching dimensions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tags', methods=['GET'])
def get_tags():
    try:
        dimension_id = request.args.get('dimension_id', type=int)
        parent_id = request.args.get('parent_id')
        level = request.args.get('level', type=int)
        
        query = """
            SELECT 
                t.id, t.dimension_id, t.name_en, t.name_zh,
                t.parent_id, t.level, t.icon_url, t.display_order,
                d.code as dimension_code,
                d.name_en as dimension_name_en,
                d.name_zh as dimension_name_zh,
                (SELECT COUNT(*) FROM file_tags ft WHERE ft.tag_id = t.id) as file_count
            FROM tags t
            JOIN dimensions d ON t.dimension_id = d.id
            WHERE t.is_active = TRUE
        """
        params = []
        
        if dimension_id:
            query += " AND t.dimension_id = %s"
            params.append(dimension_id)
        
        if parent_id == 'null' or parent_id == 'none':
            query += " AND t.parent_id IS NULL"
        elif parent_id:
            query += " AND t.parent_id = %s"
            params.append(int(parent_id))
        
        if level:
            query += " AND t.level = %s"
            params.append(level)
        
        query += " ORDER BY t.display_order, t.name_en"
        
        tags = execute_query(query, tuple(params) if params else None)
        return jsonify({'success': True, 'data': tags})
    except Exception as e:
        app.logger.error(f"Error fetching tags: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tags/tree', methods=['GET'])
def get_tags_tree():
    try:
        dimensions = execute_query("""
            SELECT id, code, name_en, name_zh, display_order
            FROM dimensions ORDER BY display_order
        """)
        
        tags = execute_query("""
            SELECT id, dimension_id, name_en, name_zh, parent_id, level, 
                   icon_url, display_order
            FROM tags WHERE is_active = TRUE
            ORDER BY level, display_order
        """)
        
        def build_tree(tags, parent_id=None):
            tree = []
            for tag in tags:
                if tag['parent_id'] == parent_id:
                    children = build_tree(tags, tag['id'])
                    tag_node = {**tag, 'children': children}
                    tree.append(tag_node)
            return tree
        
        result = {}
        for dim in dimensions:
            dim_tags = [t for t in tags if t['dimension_id'] == dim['id']]
            result[dim['code']] = {
                'dimension': dim,
                'tags': build_tree(dim_tags)
            }
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        app.logger.error(f"Error fetching tag tree: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# C-Grid cell ID to database tag name mapping
# Uses EXACT icon names so hover text matches file tags
CGRID_TO_TAGS = {
    # Row 1
    'r1c1': ['Finance'],            # Gold/Finance
    'r1c2': ['Mode'],               # Mode (1+1=0)
    'r1c3': ['Resources'],          # Resources
    'r1c4': ['Publication'],        # Publication
    'r1c5': ['Business'],           # Business
    # Row 2  
    'r2c1': ['Archive'],            # Archive (pyramid)
    'r2c2': ['System'],             # System (clock)
    'r2c3': ['Project'],            # Project (clipboard)
    'r2c4': ['Education'],          # Education (books)
    'r2c5': ['Commerce'],           # Commerce (bottles)
    # Row 3
    'r3c1': ['Language'],           # Language (ancient text)
    'r3c2': ['Network'],            # Network (boat)
    'r3c3': [],                     # Center/Name - shows all
    'r3c4': ['Post'],               # Post (mail)
    'r3c5': ['Direction'],          # Direction (arrows)
    # Row 4
    'r4c1': ['Location'],           # Location (globe)
    'r4c2': ['Experience'],         # Experience (phone)
    'r4c3': ['Tree'],               # Tree (family tree)
    'r4c4': ['Circle'],             # Circle (water/social)
    'r4c5': ['Government'],         # Government (buildings)
    # Row 5
    'r5c1': ['Neon'],               # Neon (stars)
    'r5c2': ['Dictionary'],         # Dictionary (folder)
    'r5c3': ['Job'],                # Job (astronaut)
    'r5c4': ['Organization'],       # Organization (people)
    'r5c5': ['Info'],               # Info (sun)
}

@app.route('/api/files', methods=['GET'])
def get_files():
    try:
        tag_ids_str = request.args.get('tags', '')
        user_id = request.args.get('user_id', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        tag_ids = []
        cgrid_cells = []
        user_selected_filter = False  # Track if user selected any filter
        
        if tag_ids_str:
            user_selected_filter = True  # User did select something
            for t in tag_ids_str.split(','):
                t = t.strip()
                if t:
                    try:
                        # Try parsing as numeric ID first
                        tag_ids.append(int(t))
                    except ValueError:
                        # It's a C-Grid cell ID like 'r2c4'
                        cgrid_cells.append(t)
        
        # Convert C-Grid cells to tag names, then to tag IDs
        if cgrid_cells:
            tag_names = []
            for cell in cgrid_cells:
                if cell in CGRID_TO_TAGS:
                    tag_names.extend(CGRID_TO_TAGS[cell])
            
            if tag_names:
                # Remove duplicates
                tag_names = list(set(tag_names))
                placeholders = ','.join(['%s'] * len(tag_names))
                name_query = f"""
                    SELECT id FROM tags 
                    WHERE name_en IN ({placeholders}) AND is_active = TRUE
                """
                tag_results = execute_query(name_query, tuple(tag_names))
                tag_ids.extend([r['id'] for r in tag_results])
        
        # Remove duplicate tag IDs
        tag_ids = list(set(tag_ids))
        
        # If user selected filters but no matching tags found, return empty
        if user_selected_filter and not tag_ids:
            return jsonify({
                'success': True,
                'data': [],
                'count': 0,
                'filters': {'tag_ids': [], 'user_id': user_id},
                'message': 'No matching tags found for selected categories'
            })
        
        if tag_ids:
            # Use OR logic: show files with ANY of the selected tags
            placeholders = ','.join(['%s'] * len(tag_ids))
            query = f"""
                SELECT DISTINCT
                    f.id, f.original_filename, f.mime_type, f.size_bytes,
                    f.description, f.created_at, f.storage_path,
                    u.name_en as owner_name_en, u.name_zh as owner_name_zh
                FROM files f
                JOIN users u ON f.user_id = u.id
                JOIN file_tags ft ON f.id = ft.file_id
                WHERE f.user_id = %s AND ft.tag_id IN ({placeholders})
                ORDER BY f.created_at DESC
                LIMIT %s OFFSET %s
            """
            params = [user_id] + tag_ids + [limit, offset]
        else:
            query = """
                SELECT 
                    f.id, f.original_filename, f.mime_type, f.size_bytes,
                    f.description, f.created_at, f.storage_path,
                    u.name_en as owner_name_en, u.name_zh as owner_name_zh
                FROM files f
                JOIN users u ON f.user_id = u.id
                WHERE f.user_id = %s
                ORDER BY f.created_at DESC
                LIMIT %s OFFSET %s
            """
            params = [user_id, limit, offset]
        
        files = execute_query(query, tuple(params))
        
        for file in files:
            tags_query = """
                SELECT t.id, t.name_en, t.name_zh, d.code as dimension_code
                FROM file_tags ft
                JOIN tags t ON ft.tag_id = t.id
                JOIN dimensions d ON t.dimension_id = d.id
                WHERE ft.file_id = %s
                ORDER BY d.display_order
            """
            file['tags'] = execute_query(tags_query, (file['id'],))
            if file['created_at']:
                file['created_at'] = file['created_at'].isoformat()
        
        return jsonify({
            'success': True,
            'data': files,
            'count': len(files),
            'filters': {'tag_ids': tag_ids, 'user_id': user_id}
        })
    except Exception as e:
        app.logger.error(f"Error fetching files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files/<int:file_id>', methods=['GET'])
def get_file(file_id):
    try:
        query = """
            SELECT 
                f.id, f.original_filename, f.mime_type, f.size_bytes,
                f.description, f.created_at, f.storage_path,
                u.name_en as owner_name_en, u.name_zh as owner_name_zh
            FROM files f
            JOIN users u ON f.user_id = u.id
            WHERE f.id = %s
        """
        file = execute_query(query, (file_id,), fetch_one=True)
        
        if not file:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        tags_query = """
            SELECT t.id, t.name_en, t.name_zh, t.dimension_id, d.code as dimension_code
            FROM file_tags ft
            JOIN tags t ON ft.tag_id = t.id
            JOIN dimensions d ON t.dimension_id = d.id
            WHERE ft.file_id = %s
        """
        file['tags'] = execute_query(tags_query, (file_id,))
        
        if file['created_at']:
            file['created_at'] = file['created_at'].isoformat()
        
        return jsonify({'success': True, 'data': file})
    except Exception as e:
        app.logger.error(f"Error fetching file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'}), 400
        
        user_id = request.form.get('user_id', 1, type=int)
        description = request.form.get('description', '')
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        storage_path = os.path.join(user_folder, unique_filename)
        file.save(storage_path)
        
        file_size = os.path.getsize(storage_path)
        
        query = """
            INSERT INTO files (user_id, original_filename, storage_path, mime_type, size_bytes, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        file_id = execute_query(
            query,
            (user_id, filename, storage_path, file.content_type, file_size, description),
            fetch_all=False,
            commit=True
        )
        
        return jsonify({
            'success': True,
            'data': {
                'id': file_id,
                'original_filename': filename,
                'storage_path': storage_path,
                'mime_type': file.content_type,
                'size_bytes': file_size,
                'description': description
            }
        }), 201
        
    except Exception as e:
        app.logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files/<int:file_id>/tags', methods=['POST'])
def assign_tags(file_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Request body required'}), 400
        
        user_id = data.get('user_id', 1)
        
        # Accept either tag_ids (numeric) or cgrid_cells (cell IDs)
        tag_ids = data.get('tag_ids', [])
        cgrid_cells = data.get('cgrid_cells', [])
        
        # Convert C-Grid cells to tag IDs
        if cgrid_cells:
            tag_names = []
            for cell in cgrid_cells:
                if cell in CGRID_TO_TAGS and CGRID_TO_TAGS[cell]:
                    tag_names.extend(CGRID_TO_TAGS[cell])
            
            if tag_names:
                tag_names = list(set(tag_names))
                placeholders = ','.join(['%s'] * len(tag_names))
                tag_results = execute_query(
                    f"SELECT id FROM tags WHERE name_en IN ({placeholders}) AND is_active = TRUE",
                    tuple(tag_names)
                )
                tag_ids.extend([r['id'] for r in tag_results])
        
        if not tag_ids:
            # No valid tags to assign, but that's okay
            return jsonify({
                'success': True,
                'data': {'file_id': file_id, 'tags': [], 'message': 'No matching tags found'}
            })
        
        # Remove duplicates
        tag_ids = list(set(tag_ids))
        
        file = execute_query(
            "SELECT id FROM files WHERE id = %s",
            (file_id,),
            fetch_one=True
        )
        if not file:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if data.get('replace', False):
                cursor.execute("DELETE FROM file_tags WHERE file_id = %s", (file_id,))
            
            for tag_id in tag_ids:
                try:
                    cursor.execute(
                        """INSERT INTO file_tags (file_id, tag_id, assigned_by)
                           VALUES (%s, %s, %s)
                           ON DUPLICATE KEY UPDATE assigned_at = CURRENT_TIMESTAMP""",
                        (file_id, tag_id, user_id)
                    )
                except mysql.connector.IntegrityError:
                    app.logger.warning(f"Could not assign tag {tag_id} to file {file_id}")
            
            conn.commit()
            
            cursor.execute("""
                SELECT t.id, t.name_en, t.name_zh, d.code as dimension_code
                FROM file_tags ft
                JOIN tags t ON ft.tag_id = t.id
                JOIN dimensions d ON t.dimension_id = d.id
                WHERE ft.file_id = %s
            """, (file_id,))
            tags = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': {'file_id': file_id, 'tags': tags}
            })
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        app.logger.error(f"Error assigning tags: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cgrid/navigate', methods=['GET'])
def cgrid_navigate():
    try:
        tag_ids_str = request.args.get('tags', '')
        user_id = request.args.get('user_id', 1, type=int)
        
        selected_tag_ids = []
        if tag_ids_str:
            selected_tag_ids = [int(t.strip()) for t in tag_ids_str.split(',') if t.strip()]
        
        dimensions = execute_query("""
            SELECT id, code, name_en, name_zh, display_order, icon_name
            FROM dimensions ORDER BY display_order
        """)
        
        result = []
        
        for dim in dimensions:
            tags = execute_query("""
                SELECT id, name_en, name_zh, parent_id, level, icon_url, display_order
                FROM tags
                WHERE dimension_id = %s AND is_active = TRUE
                ORDER BY level, display_order
            """, (dim['id'],))
            
            for tag in tags:
                if not selected_tag_ids:
                    count_result = execute_query("""
                        SELECT COUNT(DISTINCT f.id) as cnt
                        FROM files f
                        JOIN file_tags ft ON f.id = ft.file_id
                        WHERE f.user_id = %s AND ft.tag_id = %s
                    """, (user_id, tag['id']), fetch_one=True)
                else:
                    if tag['id'] in selected_tag_ids:
                        placeholders = ','.join(['%s'] * len(selected_tag_ids))
                        count_result = execute_query(f"""
                            SELECT COUNT(DISTINCT f.id) as cnt
                            FROM files f
                            JOIN file_tags ft ON f.id = ft.file_id
                            WHERE f.user_id = %s AND ft.tag_id IN ({placeholders})
                            GROUP BY f.id
                            HAVING COUNT(DISTINCT ft.tag_id) = %s
                        """, tuple([user_id] + selected_tag_ids + [len(selected_tag_ids)]), fetch_one=True)
                    else:
                        all_tags = selected_tag_ids + [tag['id']]
                        placeholders = ','.join(['%s'] * len(all_tags))
                        count_result = execute_query(f"""
                            SELECT COUNT(*) as cnt FROM (
                                SELECT f.id
                                FROM files f
                                JOIN file_tags ft ON f.id = ft.file_id
                                WHERE f.user_id = %s AND ft.tag_id IN ({placeholders})
                                GROUP BY f.id
                                HAVING COUNT(DISTINCT ft.tag_id) = %s
                            ) as matched
                        """, tuple([user_id] + all_tags + [len(all_tags)]), fetch_one=True)
                
                tag['file_count'] = count_result['cnt'] if count_result else 0
                tag['is_selected'] = tag['id'] in selected_tag_ids
            
            dim_result = {
                'dimension': dim,
                'tags': tags,
                'selected_tags': [t for t in tags if t['id'] in selected_tag_ids]
            }
            result.append(dim_result)
        
        if selected_tag_ids:
            placeholders = ','.join(['%s'] * len(selected_tag_ids))
            total_result = execute_query(f"""
                SELECT COUNT(*) as cnt FROM (
                    SELECT f.id
                    FROM files f
                    JOIN file_tags ft ON f.id = ft.file_id
                    WHERE f.user_id = %s AND ft.tag_id IN ({placeholders})
                    GROUP BY f.id
                    HAVING COUNT(DISTINCT ft.tag_id) = %s
                ) as matched
            """, tuple([user_id] + selected_tag_ids + [len(selected_tag_ids)]), fetch_one=True)
            total_files = total_result['cnt'] if total_result else 0
        else:
            total_result = execute_query(
                "SELECT COUNT(*) as cnt FROM files WHERE user_id = %s",
                (user_id,),
                fetch_one=True
            )
            total_files = total_result['cnt'] if total_result else 0
        
        return jsonify({
            'success': True,
            'data': {
                'dimensions': result,
                'selected_tag_ids': selected_tag_ids,
                'total_matching_files': total_files
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error in C-Grid navigation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        users = execute_query("""
            SELECT id, name_en, name_zh, email, created_at
            FROM users ORDER BY id
        """)
        for user in users:
            if user['created_at']:
                user['created_at'] = user['created_at'].isoformat()
        return jsonify({'success': True, 'data': users})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/stats', methods=['GET'])
def get_user_stats(user_id):
    try:
        stats = execute_query("""
            SELECT 
                COUNT(*) as total_files,
                SUM(size_bytes) as total_size,
                COUNT(DISTINCT ft.tag_id) as unique_tags
            FROM files f
            LEFT JOIN file_tags ft ON f.id = ft.file_id
            WHERE f.user_id = %s
        """, (user_id,), fetch_one=True)
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        execute_query("SELECT 1", fetch_one=True)
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    )