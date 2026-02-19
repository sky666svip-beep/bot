import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, random_split, ConcatDataset, TensorDataset
import matplotlib.pyplot as plt
import numpy as np
import os
import time
from sklearn.metrics import confusion_matrix

# Configuration
BATCH_SIZE = 128
LEARNING_RATE = 0.001
EPOCHS = 15 # Increased epochs for mixed data
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
MODEL_SAVE_PATH = 'ml/models/formula_cnn.pth'
CHARTS_DIR = 'ml/charts_formula'
HASY_FILE = 'ml/data/hasy_processed.pt'
EMNIST_CLASSES = 62

# Ensure directories exist
os.makedirs('ml/models', exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# 1. Dataset Loading
def get_mixed_data_loaders():
    # --- EMNIST ---
    # Same transform as before (rotate + flip)
    transform_emnist = transforms.Compose([
        lambda img: transforms.functional.rotate(img, -90),
        lambda img: transforms.functional.hflip(img),
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])

    print("Loading EMNIST...")
    emnist_train = torchvision.datasets.EMNIST(
        root='./data', split='byclass', train=True, download=True, transform=transform_emnist
    )
    emnist_test = torchvision.datasets.EMNIST(
        root='./data', split='byclass', train=False, download=True, transform=transform_emnist
    )
    
    # --- HASYv2 ---
    print(f"Loading HASYv2 from {HASY_FILE}...")
    if not os.path.exists(HASY_FILE):
        print(f"Error: {HASY_FILE} not found. Run process_hasy.py first.")
        return None, None, None, None

    # Load tensor data: (data_tensor, targets_tensor, symbol_map)
    hasy_data, hasy_targets, symbol_map = torch.load(HASY_FILE)
    
    # Custom Dataset to ensure labels are returned as int (scalar), not 0-d tensor
    class CustomTensorDataset(torch.utils.data.Dataset):
        def __init__(self, data, targets):
            self.data = data
            self.targets = targets
        def __getitem__(self, index):
            return self.data[index], self.targets[index].item()
        def __len__(self):
            return len(self.data)

    # --- Oversampling HASY ---
    # EMNIST ByClass has ~800k images (avg ~13k per class).
    # HASY has ~500 images (avg ~60 per class).
    # We need to boost HASY to match EMNIST frequency roughly.
    # Factor = 200.
    print(f"Oversampling HASY data (original size: {len(hasy_data)})...")
    oversample_factor = 200
    hasy_data_oversampled = hasy_data.repeat(oversample_factor, 1, 1, 1)
    hasy_targets_oversampled = hasy_targets.repeat(oversample_factor)
    print(f"New HASY size: {len(hasy_data_oversampled)}")

    hasy_dataset = CustomTensorDataset(hasy_data_oversampled, hasy_targets_oversampled)
    
    # Split HASY into train/test (90/10)
    hasy_len = len(hasy_dataset)
    hasy_train_len = int(0.9 * hasy_len)
    hasy_test_len = hasy_len - hasy_train_len
    hasy_train, hasy_test = random_split(hasy_dataset, [hasy_train_len, hasy_test_len])
    
    # --- Combine ---
    print(f"Combining datasets...")
    full_train_dataset = ConcatDataset([emnist_train, hasy_train])
    full_test_dataset = ConcatDataset([emnist_test, hasy_test])
    
    # Split train into train/val
    train_size = int(0.9 * len(full_train_dataset))
    val_size = len(full_train_dataset) - train_size
    train_dataset, val_dataset = random_split(full_train_dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(full_test_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    total_classes = EMNIST_CLASSES + len(symbol_map)
    print(f"Total Classes: {total_classes}")
    print(f"Train samples: {len(train_dataset)}")
    
    return train_loader, val_loader, test_loader, total_classes, symbol_map

# 2. Model Definition (Same backbone, expanded head)
class FormulaCNN(nn.Module):
    def __init__(self, num_classes):
        super(FormulaCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Dropout(0.25)
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(128 * 7 * 7, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x

# 3. Training Loop
def train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=10):
    train_losses, val_losses, val_accuracies = [], [], []
    
    start_time = time.time()
    
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        
        for images, labels in train_loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * images.size(0)
            
        epoch_loss = running_loss / len(train_loader.dataset)
        train_losses.append(epoch_loss)
        
        # Validation
        val_loss, val_acc = evaluate_model(model, val_loader, criterion)
        val_losses.append(val_loss)
        val_accuracies.append(val_acc)
        
        print(f"Epoch [{epoch+1}/{num_epochs}] Train Loss: {epoch_loss:.4f} Val Loss: {val_loss:.4f} Val Acc: {val_acc:.2f}%")
              
    total_time = time.time() - start_time
    print(f"Training completed in {total_time:.0f}s")
    
    return train_losses, val_losses, val_accuracies

def evaluate_model(model, loader, criterion):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            outputs = model(images)
            loss = criterion(outputs, labels)
            running_loss += loss.item() * images.size(0)
            
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
    avg_loss = running_loss / len(loader.dataset)
    accuracy = 100 * correct / total
    return avg_loss, accuracy

# 4. Main
if __name__ == '__main__':
    print(f"Using device: {DEVICE}")
    
    train_loader, val_loader, test_loader, num_classes, symbol_map = get_mixed_data_loaders()
    
    if train_loader:
        print("Initializing Model...")
        model = FormulaCNN(num_classes=num_classes).to(DEVICE)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
        
        # Train
        train_losses, val_losses, val_accs = train_model(
            model, train_loader, val_loader, criterion, optimizer, num_epochs=EPOCHS
        )
        
        # Test
        test_loss, test_acc = evaluate_model(model, test_loader, criterion)
        print(f"Final Test Accuracy: {test_acc:.2f}%")
        
        # Save
        torch.save({
            'model_state_dict': model.state_dict(),
            'num_classes': num_classes,
            'symbol_map': symbol_map
        }, MODEL_SAVE_PATH)
        print(f"Model saved to {MODEL_SAVE_PATH}")
        
        # Save symbol map for inference service
        torch.save(symbol_map, 'ml/models/symbol_map.pth')
