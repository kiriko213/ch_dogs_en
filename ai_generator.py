import os
import time
import google.generativeai as genai
import google.api_core.exceptions

def generate_viral_script(topic="health", channel_context="", api_key=None, feedback=None, language="en", profile_key="", past_titles=None):
    """
    【エコモード仕様】
    Googleへのリクエスト回数と送信トークンを極限まで削ぎ落とし、
    1回の実行につきAPIコールを最短・最小の1回で完結させます。
    """
    if api_key:
        import json
        from google.oauth2 import service_account

        service_account_str = os.environ.get("GEMINI_SERVICE_ACCOUNT")
        credentials = None
        if service_account_str:
            try:
                info = json.loads(service_account_str)
                credentials = service_account.Credentials.from_service_account_info(info)
            except Exception:
                if os.path.exists(service_account_str):
                    try:
                        credentials = service_account.Credentials.from_service_account_file(service_account_str)
                    except Exception:
                        pass
        if credentials:
            genai.configure(credentials=credentials)
        else:
            genai.configure(api_key=api_key)

    model = genai.GenerativeModel('gemini-1.5-flash')

    # エコモード用極短プロンプト（コンテキストを完全排除）
    if language == "ja":
        prompt = f"YouTubeショート動画用として「{topic}」に関するナレーション（100〜150文字程度）を日本語で作成してください。余計な前置きやタイトルは一切省き、ナレーションテキストのみを出力してください。"
    else:
        prompt = f"Write a 15-second narration script for a YouTube Short about '{topic}' in English. Keep it to 18-22 words. Output ONLY the narration text. No titles, no introduction, no emojis, no markdown, and no extra notes."

    print(f"[ECO_MODE] Sending minimal prompt to Gemini...")

    # 429エラー時はリトライせず、即座に例外を発生させる
    try:
        response = model.generate_content(prompt)
    except google.api_core.exceptions.ResourceExhausted as rate_e:
        print("[RATE_LIMIT] 429 ResourceExhausted detected. Immediately aborting without retry.")
        raise rate_e
    except Exception as e:
        print(f"[GENERATION_ERROR] Failed to call Gemini API: {e}")
        raise e

    content = response.text.strip()
    # 余分な改行やクォートを取り除く
    content = content.replace('"', '').replace("'", "").strip()
    
    # タイトルと検索キーワードは、プログラム側の固定テンプレート/ルールで生成
    title = f"Amazing {topic}!"
    
    # Pexelsキーワードのマッピング
    topic_lower = topic.lower()
    profile_lower = profile_key.lower() if profile_key else ""
    if "dog" in profile_lower or "puppy" in profile_lower or "dog" in topic_lower or "puppy" in topic_lower:
        keyword = "dog,puppy"
    elif "pawvana" in profile_lower or "pet" in profile_lower or "pet" in topic_lower:
        keyword = "cute pet,cat,dog"
    elif "deep sea" in topic_lower:
        keyword = "deep sea,ocean"
    elif "strange ocean" in topic_lower or "creatures" in topic_lower:
        keyword = "strange fish,marine life"
    elif "coral reef" in topic_lower:
        keyword = "coral reef,fish"
    elif "freshwater" in topic_lower:
        keyword = "freshwater fish,river"
    elif "aquarium" in topic_lower:
        keyword = "aquarium,jellyfish"
    else:
        keyword = "marine life,ocean"

    print(f"[ECO_MODE] Generated script content: {content}")
    print(f"[ECO_MODE] Generated local title: {title}")
    print(f"[ECO_MODE] Generated local search query: {keyword}")

    return title, content, keyword, None

def clean_script_text(text: str) -> str:
    import re
    if not text:
        return ""
    text = re.sub(r'(\b\w+)\s+(t\b|\btell\b)', r'\1\2', text)
    text = re.sub(r'(\bWha\b)\s+(t\'s)', r"What's", text)
    text = re.sub(r'\*\s*([^*]+)\s*\*', r'*\1*', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def _parse_json_response(text):
    # エコモードではJSONパースは行わないが、他からの呼び出しでのエラーを防ぐためにダミーを用意
    return {}

def generate_viral_scripts_batch(topic="health", api_key=None, batch_size=5, language="en", profile_key="", work_dir="."):
    """
    Gemini APIを1回呼び出し、指定されたトピックに関するShorts台本を指定数（デフォルト5本）一括生成します。
    返り値: スクリプトオブジェクトのリスト
    """
    import os
    import json
    import re
    import google.generativeai as genai

    if api_key:
        service_account_str = os.environ.get("GEMINI_SERVICE_ACCOUNT")
        credentials = None
        if service_account_str:
            try:
                info = json.loads(service_account_str)
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_info(info)
            except Exception:
                if os.path.exists(service_account_str):
                    try:
                        from google.oauth2 import service_account
                        credentials = service_account.Credentials.from_service_account_file(service_account_str)
                    except Exception:
                        pass
        if credentials:
            genai.configure(credentials=credentials)
        else:
            genai.configure(api_key=api_key)

    # JSONレスポンス出力を強制するための設定
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )

    # Dynamically build augmented prompt using performance feedback & diversity guard
    try:
        from prompt_builder import PromptBuilder
        # キャッシュの存在するカレントディレクトリを指定してビルダ初期化
        builder = PromptBuilder(work_dir=".")
        prompt = builder.build_augmented_prompt(topic, language=language, batch_size=batch_size)
    except Exception as pb_err:
        print(f"[PROMPT_BUILDER_WARN] Prompt Builder failed: {pb_err}. Falling back to default prompt.")
        if language == "ja":
            prompt = f"""
            Generate exactly {batch_size} independent YouTube Shorts narration scripts about '{topic}' in Japanese.
            Output MUST be a valid JSON array matching the schema below. No explanation, no markdown backticks, no markdown blocks.

            JSON Schema:
            [
              {{
                "topic": "サブトピック名",
                "title": "動画タイトル (50文字以内)",
                "script": "100文字から150文字程度の日本語ナレーションテキストのみ。余計な前置きや絵文字は一切除外すること。"
              }}
            ]
            """
        else:
            prompt = f"""
            Generate exactly {batch_size} independent YouTube Shorts narration scripts about '{topic}' in English.
            Output MUST be a valid JSON array matching the schema below. No explanation, no markdown backticks, no markdown blocks.

            JSON Schema:
            [
              {{
                "topic": "Specific sub-topic name",
                "title": "Video title (under 50 chars)",
                "script": "15-second narration (20 to 25 words). MUST be written in exactly 3 distinct sentences: Hook, Development, and Call to Action. MUST end with a short question asking the viewer about their own dog to drive comments. Output only the narration text, no emojis, no quotation marks."
              }}
            ]
            """

    print(f"[BATCH_MODE] Requesting {batch_size} scripts from Gemini...")
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Markdownのコードブロック記法 (```json ... ```) が含まれる場合のトリミング保護
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(?:json)?\n', '', raw_text)
            raw_text = re.sub(r'\n```$', '', raw_text)
            raw_text = raw_text.strip()
            
        items = json.loads(raw_text)
        if not isinstance(items, list):
            raise ValueError("Gemini response is not a JSON list")

        # --- Concept-duplication validation & Incremental replenishment loop ---
        from concept_guard import extract_concepts, get_uploaded_concepts
        import re as _re

        # 1. 過去のアップロード済みコンセプトの取得
        cache_path = os.path.join(work_dir, "script_cache.json")
        uploaded_concepts = get_uploaded_concepts(cache_path)
        
        seen_batch_concepts = set()
        seen_hook_frameworks = set()
        valid_items = []

        # 過去のトピック履歴および投稿済みビデオタイトルの取得
        history_list = []
        try:
            from prompt_builder import PromptBuilder
            pb = PromptBuilder(work_dir=work_dir)
            posted_titles = pb.load_posted_video_titles(limit=100)
            posted_topics = pb.load_recent_topics(limit=50)
            history_list = posted_titles + posted_topics
        except Exception as e:
            print(f"[GENERATION_GUARD_WARN] Failed to load history lists: {e}")

        import difflib
        def _is_similar_to_history(new_topic, history):
            norm_new = _normalize_topic(new_topic)
            if not norm_new:
                return False
            for hist_item in history:
                norm_hist = _normalize_topic(hist_item)
                if not norm_hist:
                    continue
                if norm_new == norm_hist:
                    return True
                if difflib.SequenceMatcher(None, norm_new, norm_hist).ratio() >= 0.7:
                    return True
                words_new = set(norm_new.split())
                words_hist = set(norm_hist.split())
                if words_new and words_hist:
                    overlap = words_new & words_hist
                    min_len = min(len(words_new), len(words_hist))
                    if min_len > 0 and len(overlap) / min_len >= 0.70:
                        return True
            return False

        # 過去のキャッシュアイテム一覧の取得
        past_items = []
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f_cache:
                    cache_data = json.load(f_cache)
                    past_items = cache_data.get("items", [])
        except Exception as e:
            print(f"[GENERATION_GUARD_WARN] Failed to load script_cache items: {e}")

        def _is_duplicate_by_meta(item, other):
            keys = ["category", "subtopic", "unique_fact", "angle", "region", "age_stage"]
            def get_val(obj, k):
                val = obj.get(k)
                if val is None:
                    return ""
                return str(val).strip().lower()

            item_vals = {k: get_val(item, k) for k in keys}
            other_vals = {k: get_val(other, k) for k in keys}

            # unique_fact が同じ場合、angle も同じなら重複
            if item_vals["unique_fact"] and item_vals["unique_fact"] == other_vals["unique_fact"]:
                if item_vals["angle"] == other_vals["angle"]:
                    return True

            diff_count = 0
            for k in keys:
                if item_vals[k] != other_vals[k]:
                    diff_count += 1

            if diff_count < 3:
                return True
            return False

        def _normalize_topic(raw):
            t = raw.lower().strip()
            t = _re.sub(r'[^a-z0-9\s]', '', t)
            t = _re.sub(r'\s+', ' ', t).strip()
            return t

        def _topics_are_near_identical(a, b):
            if a == b:
                return True
            words_a = set(a.split())
            words_b = set(b.split())
            if not words_a or not words_b:
                return False
            intersection = words_a & words_b
            smaller = min(len(words_a), len(words_b))
            if smaller > 0 and len(intersection) / smaller >= 0.90:
                return True
            return False

        # 最初の一括生成されたアイテムを検証
        for item in items:
            item_topic = item.get("topic", "")
            item_title = item.get("title", "")
            item_script = item.get("script", "")
            
            # コンセプトの抽出
            item_concepts = set()
            item_concepts.update(extract_concepts(item_topic))
            item_concepts.update(extract_concepts(item_title))
            item_concepts.update(extract_concepts(item_script))
            
            # A. 過去のアップロードとの重複チェック
            overlap_global = item_concepts.intersection(uploaded_concepts)
            if overlap_global:
                print(f"[GENERATION_GUARD] Global overlap detected for '{item_topic}': {overlap_global}. Skipping.")
                continue
                
            # B. 同一バッチ内でのコンセプト重複チェック
            overlap_batch = item_concepts.intersection(seen_batch_concepts)
            if overlap_batch:
                print(f"[GENERATION_GUARD] Batch overlap detected for '{item_topic}': {overlap_batch}. Skipping.")
                continue

            # C. トピックの厳密な類似チェック
            norm_topic = _normalize_topic(item_topic)
            is_near_identical = False
            for prev_item in valid_items:
                prev_norm = _normalize_topic(prev_item.get("topic", ""))
                if _topics_are_near_identical(norm_topic, prev_norm):
                    is_near_identical = True
                    break
            if is_near_identical:
                print(f"[GENERATION_GUARD] Near-identical topic detected for '{item_topic}'. Skipping.")
                continue

            # D. hook_framework の重複チェック
            item_framework = item.get("hook_framework")
            if item_framework:
                norm_framework = item_framework.strip().lower()
                if norm_framework in seen_hook_frameworks:
                    print(f"[GENERATION_GUARD] Duplicate hook_framework detected for '{item_topic}': '{item_framework}'. Skipping.")
                    continue

            # E. 過去の投稿履歴（トピック・タイトル）との類似チェック
            if history_list and _is_similar_to_history(item_topic, history_list):
                print(f"[GENERATION_GUARD] Topic '{item_topic}' is semantically similar to history. Skipping.")
                continue

            # F. メタデータ（6要素）による重複チェック
            is_meta_dup = False
            for past_item in past_items:
                if _is_duplicate_by_meta(item, past_item):
                    is_meta_dup = True
                    break
            if not is_meta_dup:
                for prev_item in valid_items:
                    if _is_duplicate_by_meta(item, prev_item):
                        is_meta_dup = True
                        break
            if is_meta_dup:
                print(f"[GENERATION_GUARD] Metadata duplication detected for '{item_topic}'. Skipping.")
                continue
            
            # すべてのガードを通過した場合
            valid_items.append(item)
            seen_batch_concepts.update(item_concepts)
            if item_framework:
                seen_hook_frameworks.add(item_framework.strip().lower())

        # 不足分がある場合、Gemini APIに対して再生成/補充ループを実行する (最大3回リトライ)
        max_retries = 3
        retry_count = 0
        while len(valid_items) < batch_size and retry_count < max_retries:
            needed_count = batch_size - len(valid_items)
            retry_count += 1
            print(f"[GENERATION_GUARD] Batch incomplete ({len(valid_items)}/{batch_size}). Replenishing {needed_count} items (Attempt {retry_count}/{max_retries})...")
            
            # 禁止する既存コンセプト（過去 + 現在バッチ）の一覧をプロンプト用に結合
            forbidden_list = sorted(list(uploaded_concepts.union(seen_batch_concepts)))
            forbidden_instr = ""
            if forbidden_list:
                forbidden_instr = f"\n[FORBIDDEN CONCEPTS / TOPICS]\nDo NOT generate any scripts related to the following concepts:\n"
                forbidden_instr += "\n".join([f"- {c}" for c in forbidden_list])
                forbidden_instr += "\nFocus on entirely new canine domains (e.g. nutrition, genetics, vision, hearing, reproduction) that do not overlap with the forbidden list."
            
            if seen_hook_frameworks:
                forbidden_instr += f"\n\n[USED HOOK FRAMEWORKS]\nDo NOT use the following hook_framework values (they are already used in this batch):\n"
                forbidden_instr += "\n".join([f"- {hw}" for hw in seen_hook_frameworks])
                forbidden_instr += "\nYou MUST choose from the remaining unused options of [Myth vs Fact, Problem & Solution, Secret Meaning, Warning]."

            # リトライ用のプロンプト構築
            retry_prompt = prompt
            str_batch_size = str(batch_size)
            retry_prompt = retry_prompt.replace(f"exactly {str_batch_size} independent", f"exactly {needed_count} independent")
            retry_prompt = retry_prompt.replace(f"正確に{str_batch_size}本", f"正確に{needed_count}本")
            retry_prompt = retry_prompt.replace(f"約{str_batch_size}本", f"約{needed_count}本")
            retry_prompt = retry_prompt.replace(f"of {str_batch_size} scripts", f"of {needed_count} scripts")
            retry_prompt = retry_prompt.replace(f"うち、約{str_batch_size}%", f"うち、約{needed_count}%")
            retry_prompt += "\n" + forbidden_instr
            
            try:
                # 補充リクエストの送信
                response = model.generate_content(retry_prompt)
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = re.sub(r'^```(?:json)?\n', '', raw_text)
                    raw_text = re.sub(r'\n```$', '', raw_text)
                    raw_text = raw_text.strip()
                
                new_items = json.loads(raw_text)
                if isinstance(new_items, list):
                    for item in new_items:
                        if len(valid_items) >= batch_size:
                            break
                        item_topic = item.get("topic", "")
                        item_title = item.get("title", "")
                        item_script = item.get("script", "")
                        
                        item_concepts = set()
                        item_concepts.update(extract_concepts(item_topic))
                        item_concepts.update(extract_concepts(item_title))
                        item_concepts.update(extract_concepts(item_script))
                        
                        overlap_global = item_concepts.intersection(uploaded_concepts)
                        if overlap_global:
                            print(f"[GENERATION_GUARD] [RETRY] Global overlap for '{item_topic}': {overlap_global}. Skipping.")
                            continue
                            
                        overlap_batch = item_concepts.intersection(seen_batch_concepts)
                        if overlap_batch:
                            print(f"[GENERATION_GUARD] [RETRY] Batch overlap for '{item_topic}': {overlap_batch}. Skipping.")
                            continue

                        norm_topic = _normalize_topic(item_topic)
                        is_near_identical = False
                        for prev_item in valid_items:
                            prev_norm = _normalize_topic(prev_item.get("topic", ""))
                            if _topics_are_near_identical(norm_topic, prev_norm):
                                is_near_identical = True
                                break
                        if is_near_identical:
                            print(f"[GENERATION_GUARD] [RETRY] Near-identical topic for '{item_topic}'. Skipping.")
                            continue

                        # D. hook_framework の重複チェック
                        item_framework = item.get("hook_framework")
                        if item_framework:
                            norm_framework = item_framework.strip().lower()
                            if norm_framework in seen_hook_frameworks:
                                print(f"[GENERATION_GUARD] [RETRY] Duplicate hook_framework for '{item_topic}': '{item_framework}'. Skipping.")
                                continue

                        # E. 過去の投稿履歴（トピック・タイトル）との類似チェック
                        if history_list and _is_similar_to_history(item_topic, history_list):
                            print(f"[GENERATION_GUARD] [RETRY] Topic '{item_topic}' is semantically similar to history. Skipping.")
                            continue

                        # F. メタデータ（6要素）による重複チェック
                        is_meta_dup = False
                        for past_item in past_items:
                            if _is_duplicate_by_meta(item, past_item):
                                is_meta_dup = True
                                break
                        if not is_meta_dup:
                            for prev_item in valid_items:
                                if _is_duplicate_by_meta(item, prev_item):
                                    is_meta_dup = True
                                    break
                        if is_meta_dup:
                            print(f"[GENERATION_GUARD] [RETRY] Metadata duplication for '{item_topic}'. Skipping.")
                            continue

                        # 合格した場合はマージ
                        valid_items.append(item)
                        seen_batch_concepts.update(item_concepts)
                        if item_framework:
                            seen_hook_frameworks.add(item_framework.strip().lower())
            except Exception as retry_err:
                print(f"[GENERATION_GUARD_WARN] Retry attempt {retry_count} failed: {retry_err}")
                
        if len(valid_items) < batch_size:
            print(f"[GENERATION_GUARD_WARN] Could not replenish to full batch size {batch_size}. Proceeding with {len(valid_items)} valid items.")
        else:
            print(f"[GENERATION_GUARD] Successfully established full batch of {batch_size} unique items.")

        items = valid_items
        # --- End topic-duplication validation ---

        # Pexels検索クエリの自動解決をバッチ生成時に行う
        for i, item in enumerate(items):
            llm_query = item.get("video_search_query")
            if llm_query and isinstance(llm_query, str) and llm_query.strip():
                item["search_query"] = llm_query.strip()
            else:
                item["search_query"] = "dog"
                
        return items
    except Exception as e:
        print(f"[BATCH_ERROR] Failed to generate/parse batch: {e}")
        raise e

