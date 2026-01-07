"""
============================================================================
PEACENAMES POC - BACKEND API
============================================================================
This is the Flask backend for the PeaceNames Level 1 POC.

WHAT THIS DOES:
- Provides REST API endpoints for the C-Grid navigation
- Handles file uploads and tag assignments
- Serves the frontend application

FOR A TYPICAL SOFTWARE ENGINEER:
Think of this as a standard CRUD API, but with a twist: instead of 
traditional folder-based organization, we use multi-dimensional tags.
The key insight is that a file can have multiple tags from different
"dimensions" (WHO, WHEN, WHAT, WHERE, HOW), allowing flexible navigation.

API ENDPOINTS:
- GET  /api/dimensions         - List all dimensions
- GET  /api/tags               - List tags (optionally filtered by dimension)
- GET  /api/files              - List files (filtered by selected tags)
- POST /api/files              - Upload a new file
- POST /api/files/<id>/tags    - Assign tags to a file
- GET  /api/cgrid/navigate     - C-Grid navigation (get counts per tag)

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
CORS(app)  # Enable CORS for frontend development

# Configuration from environment variables (with defaults for local dev)
app.config.update(
    # Database settings
    DB_HOST=os.environ.get('DB_HOST', 'localhost'),
    DB_PORT=int(os.environ.get('DB_PORT', 3306)),
    DB_USER=os.environ.get('DB_USER', 'root'),
    DB_PASSWORD=os.environ.get('DB_PASSWORD', 'peacenames'),
    DB_NAME=os.environ.get('DB_NAME', 'peacenames'),
    
    # File upload settings
    UPLOAD_FOLDER=os.environ.get('UPLOAD_FOLDER', './uploads'),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB max file size
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 
                        'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'mp4', 'mp3'}
)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============================================================================
# DATABASE CONNECTION POOL
# ============================================================================
# Using connection pooling for better performance under load.
# In production, you'd want more sophisticated connection management.
# ============================================================================

db_config = {
    'host': app.config['DB_HOST'],
    'port': app.config['DB_PORT'],
    'user': app.config['DB_USER'],
    'password': app.config['DB_PASSWORD'],
    'database': app.config['DB_NAME'],
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# Create connection pool (will be initialized on first request)
connection_pool = None

def get_db_pool():
    """Get or create the database connection pool."""
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
    """Get a connection from the pool."""
    return get_db_pool().get_connection()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False):
    """
    Execute a database query with proper connection handling.
    
    This helper function:
    1. Gets a connection from the pool
    2. Executes the query
    3. Fetches results (if SELECT) or commits (if INSERT/UPDATE/DELETE)
    4. Returns the connection to the pool
    
    Args:
        query: SQL query string
        params: Tuple of parameters for the query
        fetch_one: Return single row instead of all
        fetch_all: Whether to fetch results (False for INSERT/UPDATE/DELETE)
        commit: Whether to commit the transaction
    
    Returns:
        Query results or last inserted ID (for INSERT)
    """
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

# ============================================================================
# API ENDPOINTS: DIMENSIONS
# ============================================================================

@app.route('/api/dimensions', methods=['GET'])
def get_dimensions():
    """
    Get all C-Grid dimensions.
    
    WHAT ARE DIMENSIONS?
    Dimensions are the "axes" of the C-Grid - the ways you can slice your data:
    - WHO: People involved (Family, Work, Friends)
    - WHEN: Time periods (2024, 2023, etc.)
    - WHAT: Content types (Photos, Documents, Videos)
    - WHERE: Locations (Home, Office, Travel destinations)
    - HOW: Activities/Context (Vacation, Project, Celebration)
    
    Returns:
        JSON array of dimensions with bilingual names
    """
    try:
        query = """
            SELECT id, code, name_en, name_zh, display_order, icon_name
            FROM dimensions
            ORDER BY display_order
        """
        dimensions = execute_query(query)
        return jsonify({
            'success': True,
            'data': dimensions
        })
    except Exception as e:
        app.logger.error(f"Error fetching dimensions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API ENDPOINTS: TAGS
# ============================================================================

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """
    Get tags, optionally filtered by dimension.
    
    WHAT ARE TAGS?
    Tags are the values within each dimension. They form a hierarchy:
    - Dimension: WHO
      - Tag: Family (level 1)
        - Tag: Parents (level 2)
        - Tag: Children (level 2)
    
    Query Parameters:
        dimension_id: Filter by specific dimension
        parent_id: Filter by parent tag (for hierarchical navigation)
        level: Filter by hierarchy level (1 = top-level)
    
    Returns:
        JSON array of tags with bilingual names and hierarchy info
    """
    try:
        dimension_id = request.args.get('dimension_id', type=int)
        parent_id = request.args.get('parent_id')  # Can be 'null' string or int
        level = request.args.get('level', type=int)
        
        # Build query with optional filters
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
        return jsonify({
            'success': True,
            'data': tags
        })
    except Exception as e:
        app.logger.error(f"Error fetching tags: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tags/tree', methods=['GET'])
def get_tags_tree():
    """
    Get tags organized as a tree structure by dimension.
    
    This endpoint returns the full tag hierarchy, useful for
    displaying the complete tag structure in the UI.
    
    Returns:
        JSON object with dimensions as keys, each containing nested tags
    """
    try:
        # Get all dimensions
        dimensions = execute_query("""
            SELECT id, code, name_en, name_zh, display_order
            FROM dimensions ORDER BY display_order
        """)
        
        # Get all active tags
        tags = execute_query("""
            SELECT id, dimension_id, name_en, name_zh, parent_id, level, 
                   icon_url, display_order
            FROM tags WHERE is_active = TRUE
            ORDER BY level, display_order
        """)
        
        # Build tree structure
        def build_tree(tags, parent_id=None):
            """Recursively build tag tree."""
            tree = []
            for tag in tags:
                if tag['parent_id'] == parent_id:
                    children = build_tree(tags, tag['id'])
                    tag_node = {**tag, 'children': children}
                    tree.append(tag_node)
            return tree
        
        # Organize by dimension
        result = {}
        for dim in dimensions:
            dim_tags = [t for t in tags if t['dimension_id'] == dim['id']]
            result[dim['code']] = {
                'dimension': dim,
                'tags': build_tree(dim_tags)
            }
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        app.logger.error(f"Error fetching tag tree: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API ENDPOINTS: FILES
# ============================================================================

@app.route('/api/files', methods=['GET'])
def get_files():
    """
    Get files, filtered by selected tags.
    
    THIS IS THE CORE C-GRID QUERY!
    
    When a user navigates the C-Grid by clicking tags, this endpoint
    returns files that match ALL selected tags (AND logic).
    
    Example:
        GET /api/files?tags=1,13,21
        Returns files tagged with Family AND 2023 AND Photos
    
    Query Parameters:
        tags: Comma-separated list of tag IDs (AND logic)
        user_id: Filter by user (default: 1 for demo)
        limit: Max results (default: 100)
        offset: Pagination offset
    
    Returns:
        JSON array of files matching the filter criteria
    """
    try:
        # Parse query parameters
        tag_ids_str = request.args.get('tags', '')
        user_id = request.args.get('user_id', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Parse tag IDs
        tag_ids = []
        if tag_ids_str:
            tag_ids = [int(t.strip()) for t in tag_ids_str.split(',') if t.strip()]
        
        if tag_ids:
            # C-GRID FILTER QUERY
            # This is the key query that makes C-Grid work!
            # It finds files that have ALL the selected tags.
            #
            # HOW IT WORKS:
            # 1. Join files with file_tags
            # 2. Filter to only the selected tag IDs
            # 3. Group by file
            # 4. HAVING COUNT = number of tags ensures ALL tags match
            #
            # This is an AND query: file must have tag1 AND tag2 AND tag3
            
            placeholders = ','.join(['%s'] * len(tag_ids))
            query = f"""
                SELECT 
                    f.id, f.original_filename, f.mime_type, f.size_bytes,
                    f.description, f.created_at, f.storage_path,
                    u.name_en as owner_name_en, u.name_zh as owner_name_zh
                FROM files f
                JOIN users u ON f.user_id = u.id
                JOIN file_tags ft ON f.id = ft.file_id
                WHERE f.user_id = %s AND ft.tag_id IN ({placeholders})
                GROUP BY f.id
                HAVING COUNT(DISTINCT ft.tag_id) = %s
                ORDER BY f.created_at DESC
                LIMIT %s OFFSET %s
            """
            params = [user_id] + tag_ids + [len(tag_ids), limit, offset]
        else:
            # No tag filter - return all user's files
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
        
        # Get tags for each file
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
            
            # Convert datetime to string for JSON serialization
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
    """Get a single file by ID with all its tags."""
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
        
        # Get tags
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
    """
    Upload a new file to the archive.
    
    This endpoint handles file upload and initial metadata storage.
    Tags can be assigned separately via POST /api/files/<id>/tags
    
    Request:
        multipart/form-data with:
        - file: The file to upload
        - description: Optional description
        - user_id: User ID (default: 1 for demo)
    
    Returns:
        JSON with new file ID and metadata
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'}), 400
        
        # Get metadata
        user_id = request.form.get('user_id', 1, type=int)
        description = request.form.get('description', '')
        
        # Secure filename and create storage path
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        
        # Create user folder if needed
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        # Save file
        storage_path = os.path.join(user_folder, unique_filename)
        file.save(storage_path)
        
        # Get file size
        file_size = os.path.getsize(storage_path)
        
        # Insert into database
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
    """
    Assign tags to a file.
    
    THIS IS HOW FILES ENTER THE C-GRID!
    
    When you assign tags from multiple dimensions to a file, it becomes
    discoverable via C-Grid navigation. Example:
    
    POST /api/files/1/tags
    {"tag_ids": [1, 13, 21]}  # Family, 2023, Photos
    
    Now this file can be found by:
    - Clicking WHO → Family → ...
    - Clicking WHEN → 2023 → ...
    - Clicking WHAT → Photos → ...
    
    Request Body:
        JSON with tag_ids array
    
    Returns:
        JSON confirmation with assigned tags
    """
    try:
        data = request.get_json()
        if not data or 'tag_ids' not in data:
            return jsonify({'success': False, 'error': 'tag_ids required'}), 400
        
        tag_ids = data['tag_ids']
        user_id = data.get('user_id', 1)
        
        # Verify file exists
        file = execute_query(
            "SELECT id FROM files WHERE id = %s",
            (file_id,),
            fetch_one=True
        )
        if not file:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get connection for transaction
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Clear existing tags if replace mode
            if data.get('replace', False):
                cursor.execute("DELETE FROM file_tags WHERE file_id = %s", (file_id,))
            
            # Insert new tags (ignore duplicates)
            for tag_id in tag_ids:
                try:
                    cursor.execute(
                        """INSERT INTO file_tags (file_id, tag_id, assigned_by)
                           VALUES (%s, %s, %s)
                           ON DUPLICATE KEY UPDATE assigned_at = CURRENT_TIMESTAMP""",
                        (file_id, tag_id, user_id)
                    )
                except mysql.connector.IntegrityError:
                    # Tag doesn't exist or other constraint violation
                    app.logger.warning(f"Could not assign tag {tag_id} to file {file_id}")
            
            conn.commit()
            
            # Get updated tags
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
                'data': {
                    'file_id': file_id,
                    'tags': tags
                }
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

# ============================================================================
# API ENDPOINTS: C-GRID NAVIGATION
# ============================================================================

@app.route('/api/cgrid/navigate', methods=['GET'])
def cgrid_navigate():
    """
    C-Grid navigation endpoint - THE HEART OF THE POC!
    
    This endpoint powers the C-Grid browsing experience. Given the current
    tag selection, it returns:
    1. Available tags in each dimension
    2. Count of files matching if that tag is added
    
    HOW C-GRID NAVIGATION WORKS:
    
    1. User sees 5 dimensions: WHO, WHEN, WHAT, WHERE, HOW
    2. Each dimension shows available tags with file counts
    3. User clicks a tag (e.g., "Family" in WHO)
    4. System updates counts - now showing how many files match "Family" + each other tag
    5. User clicks another tag (e.g., "2023" in WHEN)
    6. Counts update again - showing files matching "Family" AND "2023" + each other tag
    7. After 3-4 clicks, user sees their specific files
    
    Query Parameters:
        tags: Comma-separated list of already-selected tag IDs
        user_id: User ID (default: 1)
    
    Returns:
        JSON with each dimension and its available tags with file counts
    """
    try:
        # Parse current selection
        tag_ids_str = request.args.get('tags', '')
        user_id = request.args.get('user_id', 1, type=int)
        
        selected_tag_ids = []
        if tag_ids_str:
            selected_tag_ids = [int(t.strip()) for t in tag_ids_str.split(',') if t.strip()]
        
        # Get all dimensions
        dimensions = execute_query("""
            SELECT id, code, name_en, name_zh, display_order, icon_name
            FROM dimensions ORDER BY display_order
        """)
        
        result = []
        
        for dim in dimensions:
            # Get tags in this dimension
            tags = execute_query("""
                SELECT id, name_en, name_zh, parent_id, level, icon_url, display_order
                FROM tags
                WHERE dimension_id = %s AND is_active = TRUE
                ORDER BY level, display_order
            """, (dim['id'],))
            
            # Calculate file counts for each tag
            for tag in tags:
                if not selected_tag_ids:
                    # No selection yet - count all files with this tag
                    count_result = execute_query("""
                        SELECT COUNT(DISTINCT f.id) as cnt
                        FROM files f
                        JOIN file_tags ft ON f.id = ft.file_id
                        WHERE f.user_id = %s AND ft.tag_id = %s
                    """, (user_id, tag['id']), fetch_one=True)
                else:
                    # Has selection - count files that match ALL selected tags AND this tag
                    # This is the key query for C-Grid narrowing!
                    
                    if tag['id'] in selected_tag_ids:
                        # This tag is already selected - count files with all selected tags
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
                        # This tag is NOT selected - count what WOULD match if added
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
            
            # Build dimension result
            dim_result = {
                'dimension': dim,
                'tags': tags,
                'selected_tags': [t for t in tags if t['id'] in selected_tag_ids]
            }
            result.append(dim_result)
        
        # Also get the matching files count
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

# ============================================================================
# API ENDPOINTS: USERS (for demo purposes)
# ============================================================================

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users (for demo dropdown)."""
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
    """Get statistics for a user (file counts, etc.)."""
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

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.route('/')
def serve_index():
    """Serve the main frontend page."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory(app.static_folder, path)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ============================================================================
# HEALTH CHECK (useful for Docker/monitoring)
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
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

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Development server
    # In production, use gunicorn: gunicorn -w 4 -b 0.0.0.0:5000 app:app
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    )
