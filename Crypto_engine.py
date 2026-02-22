"""
E2E Encryption Engine using RSA + AES Hybrid Encryption
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets


class CryptoEngine:
    """Handles all encryption/decryption operations"""
    
    @staticmethod
    def generate_rsa_keypair():
        """Generate RSA key pair for each user"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        return private_key, public_key
    
    @staticmethod
    def serialize_private_key(private_key):
        """Serialize private key to base64"""
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
    
    @staticmethod
    def serialize_public_key(public_key):
        """Serialize public key to base64"""
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    @staticmethod
    def deserialize_public_key(pem_data):
        """Deserialize public key from PEM string"""
        return serialization.load_pem_public_key(
            pem_data.encode('utf-8'),
            backend=default_backend()
        )
    
    @staticmethod
    def deserialize_private_key(pem_data):
        """Deserialize private key from PEM string"""
        return serialization.load_pem_private_key(
            pem_data.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
    
    @staticmethod
    def encrypt_message(message, recipient_public_key):
        """
        Hybrid encryption: RSA for key exchange, AES for message encryption
        Returns: base64(encrypted_aes_key + iv + encrypted_message)
        """
        # Generate random AES key and IV
        aes_key = secrets.token_bytes(32)  # 256-bit AES
        iv = secrets.token_bytes(16)       # 128-bit IV
        
        # Encrypt message with AES
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # PKCS7 padding
        padded_message = CryptoEngine._pkcs7_pad(message.encode('utf-8'), 16)
        encrypted_message = encryptor.update(padded_message) + encryptor.finalize()
        
        # Encrypt AES key with RSA
        encrypted_aes_key = recipient_public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Combine all: encrypted_aes_key (256 bytes) + iv (16 bytes) + encrypted_message
        result = base64.b64encode(encrypted_aes_key + iv + encrypted_message)
        return result.decode('utf-8')
    
    @staticmethod
    def decrypt_message(encrypted_data, private_key):
        """
        Decrypt hybrid encrypted message
        """
        try:
            data = base64.b64decode(encrypted_data)
            
            # Extract components
            encrypted_aes_key = data[:256]
            iv = data[256:272]
            encrypted_message = data[272:]
            
            # Decrypt AES key with RSA
            aes_key = private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt message with AES
            cipher = Cipher(
                algorithms.AES(aes_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded_message = decryptor.update(encrypted_message) + decryptor.finalize()
            
            # Remove padding
            message = CryptoEngine._pkcs7_unpad(padded_message)
            return message.decode('utf-8')
            
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    @staticmethod
    def _pkcs7_pad(data, block_size):
        """Add PKCS7 padding"""
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length] * padding_length)
        return data + padding
    
    @staticmethod
    def _pkcs7_unpad(data):
        """Remove PKCS7 padding"""
        padding_length = data[-1]
        return data[:-padding_length]
    
    @staticmethod
    def generate_user_id():
        """Generate unique user ID"""
        return secrets.token_hex(16)
