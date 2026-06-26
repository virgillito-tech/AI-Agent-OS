import sys
import re

if sys.platform == 'darwin':
    try:
        # Patch for Gemma 4 architectures
        import mlx_lm.models.gemma4_text as gemma4_text
        import mlx_lm.models.gemma4 as gemma4
        
        # 1. Alias per gemma4_assistant (testo puro) -> gemma4_text
        sys.modules['mlx_lm.models.gemma4_assistant'] = gemma4_text
        
        # 2. Alias per gemma4_unified (multimodale nativo) -> gemma4
        sys.modules['mlx_lm.models.gemma4_unified'] = gemma4
        
        # Patch the sanitize method ONLY for gemma4_assistant/text if needed
        original_sanitize = gemma4_text.Model.sanitize
        def patched_sanitize(self, weights):
            sanitized = original_sanitize(self, weights)
            first_kv_shared = self.args.num_hidden_layers - getattr(self.args, 'num_kv_shared_layers', 0)
            filtered = {}
            for k, v in sanitized.items():
                if any(k.startswith(prefix) for prefix in ("masked_embedding.", "pre_projection.", "post_projection.")):
                    continue
                match = re.search(r"layers\.(\d+)\.self_attn\.(k_proj|v_proj|k_norm|v_norm)", k)
                if match:
                    layer_idx = int(match.group(1))
                    if layer_idx >= first_kv_shared:
                        continue
                filtered[k] = v
            return filtered

        # Bugfix per gemma4 nativo: mlx_lm dimentica di filtrare 'vision_embedder'
        original_gemma4_sanitize = gemma4.Model.sanitize
        def patched_gemma4_sanitize(self, weights):
            filtered_weights = {
                k: v for k, v in weights.items() 
                if not k.startswith(("vision_embedder.", "mm_projector."))
            }
            return original_gemma4_sanitize(self, filtered_weights)
        
        gemma4.Model.sanitize = patched_gemma4_sanitize
        gemma4_text.Model.sanitize = patched_sanitize
        print("⚡ [PATCH] Applicati alias nativi e patch per Gemma 4 (Unified & Assistant).")
    except Exception as e:
        print(f"⚠️ [PATCH WARNING] Impossibile applicare la patch Gemma 4: {e}")

    # Import and execute the standard mlx_lm server entry point
    try:
        import mlx_lm.server as server
        if __name__ == "__main__":
            server.main()
    except ImportError:
        pass
