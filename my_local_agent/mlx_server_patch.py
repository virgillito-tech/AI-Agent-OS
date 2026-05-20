# Patch wrapper for MLX server to handle Gemma 4 KV layer mismatches
import sys
import re

try:
    # Attempt to import mlx_lm and patch the sanitize method to prevent strict weight load crashes on Gemma 4
    import mlx_lm.models.gemma4_text as gemma4_text
    
    original_sanitize = gemma4_text.Model.sanitize

    def patched_sanitize(self, weights):
        # Apply original sanitize logic
        sanitized = original_sanitize(self, weights)
        
        # Filter out redundant KV projection and normalization layers that are not defined in the model architecture
        first_kv_shared = self.args.num_hidden_layers - self.args.num_kv_shared_layers
        filtered = {}
        for k, v in sanitized.items():
            match = re.search(r"layers\.(\d+)\.self_attn\.(k_proj|v_proj|k_norm|v_norm)", k)
            if match:
                layer_idx = int(match.group(1))
                if layer_idx >= first_kv_shared:
                    # Drop this key to prevent ValueError during strict weight loading
                    continue
            filtered[k] = v
        return filtered

    gemma4_text.Model.sanitize = patched_sanitize
    print("⚡ [PATCH] Applicata patch di compatibilità per Gemma 4 KV-sharing.")
except Exception as e:
    print(f"⚠️ [PATCH WARNING] Impossibile applicare la patch Gemma 4: {e}")

# Import and execute the standard mlx_lm server entry point
import mlx_lm.server as server
if __name__ == "__main__":
    server.main()
