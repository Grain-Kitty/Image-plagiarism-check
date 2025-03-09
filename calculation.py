import os
import threading
from PIL import Image
import imagehash
import time
from concurrent.futures import ThreadPoolExecutor
import pillow_heif
import traceback

# 注册 HEIF 解码器
pillow_heif.register_heif_opener()


def get_file_type(image_path):
    with open(image_path, "rb") as f:
        header = f.read(12)  # 读取前 12 个字节
        if header.hex().startswith("0000001c667479706865"):  # HEIF 文件头
            return "HEIF"
        elif header.startswith(b"\xff\xd8\xff"):  # JPEG 文件头
            return "JPEG"
        elif header.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG 文件头
            return "PNG"
        elif header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):  # GIF 文件头
            return "GIF"
        else:
            return "Unknown"


def calculate_hashes(image_path):
    """
    计算图像的PHash和DHash值
    :param image_path: 图像文件的路径
    :return: PHash和DHash值
    """
    try:
        img = Image.open(image_path)
        p_hash = imagehash.phash(img)
        d_hash = imagehash.dhash(img)
        return p_hash, d_hash
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        # 可以添加更多信息，如文件大小、文件头信息等
        try:
            file_size = os.path.getsize(image_path)
            print(f"File size: {file_size} bytes")
            with open(image_path, 'rb') as f:
                file_header = f.read(10).hex()
                print(f"File header: {file_header}")
        except Exception as inner_e:
            print(f"Error getting file info: {inner_e}")
        return None, None


class HashCalculator:
    result_file_path = "image_hashes.txt"

    def __init__(self):
        pass

    def has_existing_hashes(self):
        return os.path.exists(self.result_file_path)

    def calculate_hashes(self, folder_path, progress_callback, completion_callback):
        image_paths = self._find_images(folder_path)
        total_files = len(image_paths)

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._generate_hashes, path) for path in image_paths]
            with open(self.result_file_path, 'w', encoding='utf-8') as result_file:
                for i, future in enumerate(futures, start=1):
                    result = future.result()
                    if result:
                        image_path, hashes = result
                        output = self._format_hash_output(image_path, hashes)
                        result_file.write(output)
                    progress_callback(i / total_files * 100)
        completion_callback(True)

    def _find_images(self, folder_path):
        return [os.path.join(root, file)
                for root, _, files in os.walk(folder_path)
                for file in files
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.heic'))]

    def _generate_hashes(self, image_path):
        file_type = get_file_type(image_path)
        if file_type == "Unknown":
            print(f"Skipping unrecognized file: {image_path}")
            return None
        p_hash, d_hash = calculate_hashes(image_path)
        if p_hash is None or d_hash is None:
            return None
        hashes = {
            "PHash": str(p_hash),
            "DHash": str(d_hash),
            "WHash": str(imagehash.whash(Image.open(image_path))),
            "AHash": str(imagehash.average_hash(Image.open(image_path)))
        }
        return image_path, hashes

    def _format_hash_output(self, image_path, hashes):
        return f"Image: {image_path}\n" + "\n".join(
            f"{k}: {v}" for k, v in hashes.items()
        ) + "\n\n"


class DuplicateAnalyzer:
    def __init__(self):
        pass

    def find_duplicates(self, completion_callback):
        all_image_hashes = self._parse_hash_file()
        duplicate_groups, suspicious_groups = self._find_duplicates_and_suspicious(all_image_hashes)
        completion_callback(duplicate_groups, suspicious_groups, all_image_hashes)

    def _parse_hash_file(self):
        all_image_hashes = {}
        current_image = ""
        with open("image_hashes.txt", 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith("Image: "):
                    current_image = line[7:]
                    all_image_hashes[current_image] = {}
                elif line:
                    hash_type, hash_value = line.split(": ")
                    all_image_hashes[current_image][hash_type] = hash_value
        return all_image_hashes

    def _find_duplicates_and_suspicious(self, all_image_hashes):
        duplicate_groups = []
        suspicious_groups = []
        image_paths = list(all_image_hashes.keys())
        grouped_images = set()

        for i in range(len(image_paths)):
            if image_paths[i] in grouped_images:
                continue
            duplicate_group = [image_paths[i]]
            suspicious_group = []

            for j in range(i + 1, len(image_paths)):
                if image_paths[j] in grouped_images:
                    continue
                img1_hashes = all_image_hashes[image_paths[i]]
                img2_hashes = all_image_hashes[image_paths[j]]

                all_matching = all(img1_hashes[ht] == img2_hashes[ht] for ht in img1_hashes)
                some_matching = any(img1_hashes[ht] == img2_hashes[ht] for ht in img1_hashes)

                if all_matching:
                    duplicate_group.append(image_paths[j])
                    grouped_images.add(image_paths[j])
                elif some_matching:
                    if image_paths[i] not in suspicious_group:
                        suspicious_group.append(image_paths[i])
                    suspicious_group.append(image_paths[j])
                    grouped_images.add(image_paths[j])

            if len(duplicate_group) > 1:
                duplicate_groups.append(duplicate_group)
            if len(suspicious_group) > 1:
                suspicious_groups.append(suspicious_group)

        return duplicate_groups, suspicious_groups
