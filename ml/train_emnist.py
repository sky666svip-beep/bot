import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, random_split
import matplotlib.pyplot as plt
import numpy as np
import os
import time
from sklearn.metrics import confusion_matrix
# import seaborn as sns

# Configuration
BATCH_SIZE = 128
LEARNING_RATE = 0.001
EPOCHS = 10
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
MODEL_SAVE_PATH = 'ml/models/emnist_cnn.pth'
CHARTS_DIR = 'ml/charts'

# Ensure directories exist
os.makedirs('ml/models', exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# 1. Dataset & DataLoader
def get_data_loaders():
    # EMNIST images are by default rotated 90 degrees and flipped.
    # We need to correct this so they look like normal characters.
    transform = transforms.Compose([
        lambda img: transforms.functional.rotate(img, -90),
        lambda img: transforms.functional.hflip(img),
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)) # Standard MNIST/EMNIST normalization
    ])

    print("Downloading EMNIST dataset (this may take a while)...")
    try:
        full_dataset = torchvision.datasets.EMNIST(
            root='./data', 
            split='byclass', 
            train=True, 
            download=True, 
            transform=transform
        )
        
        test_dataset = torchvision.datasets.EMNIST(
            root='./data', 
            split='byclass', 
            train=False, 
            download=True, 
            transform=transform
        )
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return None, None, None

    # Mapping: 0-9 (digits), 10-35 (A-Z), 36-61 (a-z)
    # Total 62 classes
    
    # Split train into train/val (90/10)
    train_size = int(0.9 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2 if os.name != 'nt' else 0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2 if os.name != 'nt' else 0)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2 if os.name != 'nt' else 0)

    print(f"Data loaded: Train={len(train_dataset)}, Val={len(val_dataset)}, Test={len(test_dataset)}")
    return train_loader, val_loader, test_loader, full_dataset.classes

# 2. Visualize Samples
def save_sample_images(loader, classes):
    dataiter = iter(loader)
    images, labels = next(dataiter)
    images = images[:16] # Take first 16
    labels = labels[:16]

    fig = plt.figure(figsize=(10, 10))
    for i in range(16):
        ax = fig.add_subplot(4, 4, i+1)
        img = images[i].squeeze()
        # Un-normalize for display
        img = img * 0.3081 + 0.1307
        ax.imshow(img, cmap='gray')
        
        # Mapping logic (EMNIST 'byclass' mapping)
        # 0-9: digits
        # 10-35: A-Z
        # 36-61: a-z
        label_idx = labels[i].item()
        if 0 <= label_idx <= 9:
            label_char = str(label_idx)
        elif 10 <= label_idx <= 35:
            label_char = chr(label_idx - 10 + ord('A'))
        elif 36 <= label_idx <= 61:
            label_char = chr(label_idx - 36 + ord('a'))
        else:
            label_char = '?'
            
        ax.set_title(f"Label: {label_char}")
        ax.axis('off')
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'sample_inputs.png'))
    plt.close()
    print(f"Saved sample images to {CHARTS_DIR}/sample_inputs.png")

# 3. Model Definition
class EMNISTCNN(nn.Module):
    def __init__(self, num_classes=62):
        super(EMNISTCNN, self).__init__()
        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 28x28 -> 14x14
            
            # Block 2
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 14x14 -> 7x7
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
        x = x.view(x.size(0), -1) # Flatten
        x = self.classifier(x)
        return x

# 4. Training Loop
def train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=10):
    train_losses = []
    val_losses = []
    val_accuracies = []
    
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
        
        # Validation phase
        val_loss, val_acc = evaluate_model(model, val_loader, criterion)
        val_losses.append(val_loss)
        val_accuracies.append(val_acc)
        
        print(f"Epoch [{epoch+1}/{num_epochs}] "
              f"Train Loss: {epoch_loss:.4f} "
              f"Val Loss: {val_loss:.4f} "
              f"Val Acc: {val_acc:.2f}%")
              
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

# 5. Visualization
def plot_metrics(train_losses, val_losses, val_accuracies):
    plt.figure(figsize=(12, 5))
    
    # Loss Plot
    plt.subplot(1, 2, 1)
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Val Loss')
    plt.title('Training & Validation Loss')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()
    
    # Accuracy Plot
    plt.subplot(1, 2, 2)
    plt.plot(val_accuracies, label='Val Accuracy', color='green')
    plt.title('Validation Accuracy')
    plt.xlabel('Epochs')
    plt.ylabel('Accuracy (%)')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'training_curves.png'))
    plt.close()
    print(f"Saved training curves to {CHARTS_DIR}/training_curves.png")

def plot_confusion_matrix(model, loader, classes):
    model.eval()
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(DEVICE)
            outputs = model(images)
            _, predicted = torch.max(outputs, 1)
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.numpy())
    
    cm = confusion_matrix(all_labels, all_preds)
    
    plt.figure(figsize=(20, 16))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix')
    plt.colorbar()
    
    # Tick marks
    tick_marks = np.arange(len(classes))
    # EMNIST classes might be just indices if we don't map them back to chars for the plot immediately
    # For clarity, let's just plot indices if list is too long, or try to be clever.
    # Given 62 classes, detailed labels might clutter. We'll stick to indices or basic layout.
    
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'confusion_matrix.png'))
    plt.close()
    print(f"Saved confusion matrix to {CHARTS_DIR}/confusion_matrix.png")

# Main Execution
if __name__ == '__main__':
    print(f"Using device: {DEVICE}")
    
    # 1. Load Data
    train_loader, val_loader, test_loader, classes = get_data_loaders()
    if train_loader is None:
        exit(1)
        
    # 2. Visualize Inputs
    save_sample_images(train_loader, classes)
    
    # 3. Initialize Model
    model = EMNISTCNN(num_classes=62).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    # 4. Train
    train_losses, val_losses, val_accuracies = train_model(
        model, train_loader, val_loader, criterion, optimizer, num_epochs=EPOCHS
    )
    
    # 5. Save Results
    plot_metrics(train_losses, val_losses, val_accuracies)
    
    # 6. Evaluate on Test Set
    test_loss, test_acc = evaluate_model(model, test_loader, criterion)
    print(f"Final Test Accuracy: {test_acc:.2f}%")
    
    # 7. Confusion Matrix
    plot_confusion_matrix(model, test_loader, classes)
    
    # 8. Save Model
    torch.save(model.state_dict(), MODEL_SAVE_PATH)
    print(f"Model saved to {MODEL_SAVE_PATH}")
